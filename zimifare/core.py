"""ZimiFare application logic and SQLite persistence.

This module intentionally has no Streamlit imports, so business rules can be tested
independently of the user interface. All amounts are integer cents (JMD).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

MAX_USERS = 1_000
MAX_RIDES = 100
MAX_TRANSACTIONS = 10_000
FRAUD_THRESHOLD_CENTS = 5_000_000  # strictly greater than JMD 50,000.00
CURRENCY = "JMD"
PBKDF2_ITERATIONS = 310_000


class ZimiFareError(Exception):
    """A safe, human-readable application error."""


class AccessDenied(ZimiFareError):
    pass


def require_text(value: str, label: str, max_length: int = 180) -> str:
    value = (value or "").strip()
    if not value:
        raise ZimiFareError(f"{label} is required.")
    if len(value) > max_length:
        raise ZimiFareError(f"{label} must be {max_length} characters or fewer.")
    return value


def email_normalized(value: str) -> str:
    email = require_text(value, "Email", 254).lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ZimiFareError("Enter a valid email address.")
    return email


def cents_from_input(value: str) -> int:
    """Parse a positive monetary amount without ever using binary floating point."""
    raw = str(value).strip().replace(",", "")
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", raw):
        raise ZimiFareError("Enter an amount such as 250 or 250.00 (up to 2 decimals).")
    try:
        cents = int(Decimal(raw) * 100)
    except (InvalidOperation, ValueError, OverflowError):
        raise ZimiFareError("Invalid monetary amount.") from None
    if not (0 < cents < 9_000_000_000_000):
        raise ZimiFareError("Amount must be positive and within the supported range.")
    return cents


def money(cents: int) -> str:
    c = int(cents)
    sign = "-" if c < 0 else ""
    c = abs(c)
    return f"{sign}{CURRENCY} {c // 100:,}.{c % 100:02d}"


def password_hash(password: str) -> str:
    if len(password) < 8:
        raise ZimiFareError("Password must contain at least 8 characters.")
    if len(password) > 256:
        raise ZimiFareError("Password is too long.")
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def password_verify(password: str, stored: str) -> bool:
    try:
        algorithm, iteration_str, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        derived = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iteration_str)
        )
        return hmac.compare_digest(derived, bytes.fromhex(digest_hex))
    except (TypeError, ValueError):
        return False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ZimiFareStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        path = str(db_path or os.getenv("ZIMIFARE_DB_PATH", "data/zimifare.db"))
        self.db_path = Path(path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=20, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=20000")
        return conn

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            # Single-writer locking prevents two simultaneous requests from settling
            # the same unpaid ride or overspending the same passenger balance.
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                phone_num TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('PASSENGER','DRIVER','ADMIN')),
                status TEXT NOT NULL DEFAULT 'ACTIVE'
                   CHECK(status IN ('ACTIVE','DISABLED','BLOCKED')),
                balance_cents INTEGER NOT NULL DEFAULT 0 CHECK(balance_cents >= 0)
            );
            CREATE TABLE IF NOT EXISTS rides (
                ride_id INTEGER PRIMARY KEY AUTOINCREMENT,
                passenger_id INTEGER NOT NULL REFERENCES users(user_id),
                driver_id INTEGER NOT NULL REFERENCES users(user_id),
                ride_date TEXT NOT NULL,
                pickup TEXT NOT NULL,
                destination TEXT NOT NULL,
                fare_cents INTEGER NOT NULL CHECK(fare_cents > 0),
                payment_status TEXT NOT NULL DEFAULT 'UNPAID'
                    CHECK(payment_status IN ('UNPAID','PAID')),
                payment_method TEXT NOT NULL DEFAULT 'NONE'
                    CHECK(payment_method IN ('NONE','FARE_CARD','CASH')),
                transaction_id INTEGER UNIQUE
            );
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_type TEXT NOT NULL CHECK(tx_type IN ('TOP_UP','FARE_PAYMENT')),
                passenger_id INTEGER NOT NULL REFERENCES users(user_id),
                driver_id INTEGER REFERENCES users(user_id),
                ride_id INTEGER REFERENCES rides(ride_id),
                amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
                method TEXT NOT NULL
                    CHECK(method IN ('SIMULATED_TOP_UP','FARE_CARD','CASH')),
                recorded_by INTEGER NOT NULL REFERENCES users(user_id),
                recorded_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'SUCCESS' CHECK(status = 'SUCCESS'),
                flagged INTEGER NOT NULL DEFAULT 0 CHECK(flagged IN (0,1))
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_payment_per_ride
                ON transactions(ride_id) WHERE tx_type = 'FARE_PAYMENT';
            CREATE INDEX IF NOT EXISTS idx_rides_passenger ON rides(passenger_id);
            CREATE INDEX IF NOT EXISTS idx_rides_driver ON rides(driver_id);
            CREATE INDEX IF NOT EXISTS idx_transactions_passenger ON transactions(passenger_id);
            """)
        finally:
            conn.close()

    @staticmethod
    def _safe_user(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        d = dict(row)
        d.pop("password_hash", None)
        return d

    @staticmethod
    def _record(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row else None

    @staticmethod
    def _records(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(r) for r in rows]

    @staticmethod
    def _require_active(conn: sqlite3.Connection, uid: int, role: str | None = None) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (uid,)).fetchone()
        if not row or row["status"] != "ACTIVE" or (role and row["role"] != role):
            raise AccessDenied("Access denied. Please sign in using an active, authorised account.")
        return row

    def has_admin(self) -> bool:
        with self._read() as conn:
            return conn.execute("SELECT EXISTS(SELECT 1 FROM users WHERE role = 'ADMIN')").fetchone()[0] == 1

    def bootstrap_admin(self, full_name: str, email: str, phone: str, password: str, *, trusted_setup: bool = False) -> int:
        if not trusted_setup:
            raise AccessDenied("Initial administrator setup must be authorised.")
        name, norm_email, number = require_text(full_name, "Full name"), email_normalized(email), require_text(phone, "Phone", 40)
        hashed = password_hash(password)
        with self._write() as conn:
            if conn.execute("SELECT 1 FROM users WHERE role='ADMIN' LIMIT 1").fetchone():
                raise ZimiFareError("An administrator has already been created.")
            cur = conn.execute(
                "INSERT INTO users(full_name,email,phone_num,password_hash,role) VALUES(?,?,?,?, 'ADMIN')",
                (name, norm_email, number, hashed),
            )
            return int(cur.lastrowid)

    def create_administrator(self, actor_id: int, current_password: str, full_name: str,
                             email: str, phone: str, password: str) -> int:
        """Add another admin, authorised by an active admin re-entering their password.

        This extends the pseudocode's one-time BootstrapAdmin without weakening
        the restriction against public registration of administrator accounts.
        """
        name = require_text(full_name, "Full name")
        norm_email = email_normalized(email)
        number = require_text(phone, "Phone", 40)
        hashed = password_hash(password)
        with self._write() as conn:
            actor = self._require_active(conn, actor_id, "ADMIN")
            if not password_verify(current_password, actor["password_hash"]):
                raise AccessDenied("Your administrator password is incorrect.")
            if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] >= MAX_USERS:
                raise ZimiFareError("User storage is full.")
            try:
                result = conn.execute(
                    "INSERT INTO users(full_name,email,phone_num,password_hash,role) "
                    "VALUES(?,?,?,?, 'ADMIN')",
                    (name, norm_email, number, hashed),
                )
            except sqlite3.IntegrityError as exc:
                if "UNIQUE" in str(exc):
                    raise ZimiFareError("This email address is already registered.") from None
                raise
            return int(result.lastrowid)

    def register(self, full_name: str, email: str, phone: str, password: str, role: str) -> int:
        if role not in ("PASSENGER", "DRIVER"):
            raise ZimiFareError("Public registration is available for passengers and drivers only.")
        name, norm_email, number = require_text(full_name, "Full name"), email_normalized(email), require_text(phone, "Phone", 40)
        hashed = password_hash(password)
        with self._write() as conn:
            if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] >= MAX_USERS:
                raise ZimiFareError("User storage is full.")
            try:
                cur = conn.execute(
                    "INSERT INTO users(full_name,email,phone_num,password_hash,role) VALUES(?,?,?,?,?)",
                    (name, norm_email, number, hashed, role),
                )
            except sqlite3.IntegrityError as exc:
                if "UNIQUE" in str(exc):
                    raise ZimiFareError("This email address is already registered.") from None
                raise
            return int(cur.lastrowid)

    def login(self, email: str, password: str) -> dict[str, Any]:
        # Same message for invalid email/password to avoid leaking registered emails.
        normalized = str(email or "").strip().lower()
        with self._read() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
        if not row or not password_verify(password, row["password_hash"]):
            raise ZimiFareError("Incorrect email or password.")
        if row["status"] != "ACTIVE":
            raise AccessDenied("Your account is disabled or blocked. Contact an administrator.")
        return self._safe_user(row)  # type: ignore[return-value]

    def current_user(self, user_id: int) -> dict[str, Any] | None:
        with self._read() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            return self._safe_user(row)

    def update_profile(self, user_id: int, name: str = "", phone: str = "", new_password: str = "", current_password: str = "") -> None:
        name = (name or "").strip()
        phone = (phone or "").strip()
        if name:
            name = require_text(name, "Name")
        if phone:
            phone = require_text(phone, "Phone", 40)
        if not (name or phone or new_password):
            raise ZimiFareError("Enter at least one change.")
        with self._write() as conn:
            row = self._require_active(conn, user_id)
            new_hash = row["password_hash"]
            if new_password:
                if not password_verify(current_password, row["password_hash"]):
                    raise ZimiFareError("Your current password is incorrect.")
                new_hash = password_hash(new_password)
            conn.execute(
                "UPDATE users SET full_name=?, phone_num=?, password_hash=? WHERE user_id=?",
                (name or row["full_name"], phone or row["phone_num"], new_hash, user_id),
            )

    def top_up(self, passenger_id: int, amount_cents: int) -> tuple[int, int]:
        if not isinstance(amount_cents, int) or amount_cents <= 0:
            raise ZimiFareError("Top-up amount must be positive.")
        with self._write() as conn:
            user = self._require_active(conn, passenger_id, "PASSENGER")
            if conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] >= MAX_TRANSACTIONS:
                raise ZimiFareError("Transaction storage is full; balance unchanged.")
            transaction = conn.execute(
                """INSERT INTO transactions
                    (tx_type,passenger_id,amount_cents,method,recorded_by,recorded_at,flagged)
                    VALUES('TOP_UP',?,?,'SIMULATED_TOP_UP',?,?,?)""",
                (passenger_id, amount_cents, passenger_id, _utc_now(), int(amount_cents > FRAUD_THRESHOLD_CENTS)),
            )
            new_balance = int(user["balance_cents"]) + amount_cents
            conn.execute("UPDATE users SET balance_cents=? WHERE user_id=?", (new_balance, passenger_id))
            return int(transaction.lastrowid), new_balance

    def create_ride(self, driver_id: int, passenger_id: int, ride_date: str, pickup: str, destination: str, fare_cents: int) -> int:
        pickup, destination = require_text(pickup, "Pickup location"), require_text(destination, "Destination")
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(ride_date)):
                raise ValueError("Wrong date format")
            date.fromisoformat(ride_date)
        except (ValueError, TypeError):
            raise ZimiFareError("Ride date must be a valid date in YYYY-MM-DD format.") from None
        if not isinstance(fare_cents, int) or fare_cents <= 0:
            raise ZimiFareError("The agreed fare must be positive.")
        with self._write() as conn:
            self._require_active(conn, driver_id, "DRIVER")
            self._require_active(conn, passenger_id, "PASSENGER")
            if conn.execute("SELECT COUNT(*) FROM rides").fetchone()[0] >= MAX_RIDES:
                raise ZimiFareError("Ride storage is full (100 rides in this prototype).")
            cur = conn.execute(
                "INSERT INTO rides(passenger_id,driver_id,ride_date,pickup,destination,fare_cents) VALUES(?,?,?,?,?,?)",
                (passenger_id, driver_id, ride_date, pickup, destination, fare_cents),
            )
            return int(cur.lastrowid)

    def settle_ride(self, actor_id: int, ride_id: int, method: str) -> tuple[int, int | None]:
        """Atomically record fare payment exactly once; return (transaction id, balance)."""
        if method not in ("FARE_CARD", "CASH"):
            raise ZimiFareError("Invalid fare payment method.")
        with self._write() as conn:
            role = "PASSENGER" if method == "FARE_CARD" else "DRIVER"
            actor = self._require_active(conn, actor_id, role)
            ride = conn.execute("SELECT * FROM rides WHERE ride_id=?", (ride_id,)).fetchone()
            if not ride:
                raise ZimiFareError("Ride not found.")
            owner = ride["passenger_id"] if method == "FARE_CARD" else ride["driver_id"]
            if owner != actor_id:
                raise AccessDenied("This ride does not belong to your account.")
            self._require_active(conn, ride["passenger_id"], "PASSENGER")
            self._require_active(conn, ride["driver_id"], "DRIVER")
            if ride["payment_status"] == "PAID":
                raise ZimiFareError("This ride has already been paid. No additional charge was made.")
            if conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] >= MAX_TRANSACTIONS:
                raise ZimiFareError("Transaction storage is full; payment unchanged.")
            amount = int(ride["fare_cents"])
            balance = None
            if method == "FARE_CARD":
                if int(actor["balance_cents"]) < amount:
                    raise ZimiFareError("Insufficient fare-card balance. Top up and retry this ride.")
                balance = int(actor["balance_cents"]) - amount
            tx = conn.execute(
                """INSERT INTO transactions(tx_type,passenger_id,driver_id,ride_id,amount_cents,
                      method,recorded_by,recorded_at,flagged)
                    VALUES('FARE_PAYMENT',?,?,?,?,?,?,?,?)""",
                (ride["passenger_id"], ride["driver_id"], ride_id, amount,
                 method, actor_id, _utc_now(), int(amount > FRAUD_THRESHOLD_CENTS)),
            )
            if method == "FARE_CARD":
                conn.execute("UPDATE users SET balance_cents=? WHERE user_id=?", (balance, actor_id))
            conn.execute(
                "UPDATE rides SET payment_status='PAID', payment_method=?, transaction_id=? WHERE ride_id=? AND payment_status='UNPAID'",
                (method, int(tx.lastrowid), ride_id),
            )
            return int(tx.lastrowid), balance

    def passengers(self, driver_id: int) -> list[dict[str, Any]]:
        with self._read() as conn:
            self._require_active(conn, driver_id, "DRIVER")
            return self._records(conn.execute(
                "SELECT user_id,full_name,email FROM users WHERE role='PASSENGER' AND status='ACTIVE' ORDER BY full_name"
            ).fetchall())

    def list_rides(self, actor_id: int) -> list[dict[str, Any]]:
        with self._read() as conn:
            user = self._require_active(conn, actor_id)
            if user["role"] not in ("PASSENGER", "DRIVER"):
                raise AccessDenied("Ride history is available for passengers and drivers.")
            field = "r.passenger_id" if user["role"] == "PASSENGER" else "r.driver_id"
            query = f"""SELECT r.*, p.full_name AS passenger_name, d.full_name AS driver_name
                FROM rides r JOIN users p ON p.user_id=r.passenger_id
                JOIN users d ON d.user_id=r.driver_id
                WHERE {field}=? ORDER BY r.ride_date DESC,r.ride_id DESC"""
            return self._records(conn.execute(query, (actor_id,)).fetchall())

    def get_ride(self, actor_id: int, ride_id: int) -> dict[str, Any] | None:
        return next((r for r in self.list_rides(actor_id) if r["ride_id"] == ride_id), None)

    def passenger_transactions(self, passenger_id: int) -> list[dict[str, Any]]:
        with self._read() as conn:
            self._require_active(conn, passenger_id, "PASSENGER")
            return self._records(conn.execute(
                "SELECT * FROM transactions WHERE passenger_id=? ORDER BY transaction_id DESC", (passenger_id,)
            ).fetchall())

    def driver_earnings(self, driver_id: int) -> dict[str, Any]:
        rides = self.list_rides(driver_id)
        paid = [r for r in rides if r["payment_status"] == "PAID"]
        return {"paid_count": len(paid), "total_cents": sum(r["fare_cents"] for r in paid), "rides": paid}

    def system_totals(self, admin_id: int) -> dict[str, Any]:
        with self._read() as conn:
            self._require_active(conn, admin_id, "ADMIN")
            out = {}
            for key, query in {
                "users": "SELECT COUNT(*) FROM users",
                "passengers": "SELECT COUNT(*) FROM users WHERE role='PASSENGER'",
                "drivers": "SELECT COUNT(*) FROM users WHERE role='DRIVER'",
                "rides": "SELECT COUNT(*) FROM rides",
                "paid_rides": "SELECT COUNT(*) FROM rides WHERE payment_status='PAID'",
                "transactions": "SELECT COUNT(*) FROM transactions",
                "flagged": "SELECT COUNT(*) FROM transactions WHERE flagged=1",
                "fares_cents": "SELECT COALESCE(SUM(fare_cents),0) FROM rides WHERE payment_status='PAID'",
            }.items():
                out[key] = conn.execute(query).fetchone()[0]
            return out

    def admin_list_rides(self, admin_id: int) -> list[dict[str, Any]]:
        """Read-only cross-account ride report for active administrators."""
        with self._read() as conn:
            self._require_active(conn, admin_id, "ADMIN")
            return self._records(conn.execute("""
                SELECT r.*, p.full_name AS passenger_name,
                       d.full_name AS driver_name
                FROM rides r
                JOIN users p ON p.user_id = r.passenger_id
                JOIN users d ON d.user_id = r.driver_id
                ORDER BY r.ride_date DESC, r.ride_id DESC
            """).fetchall())

    def list_users(self, admin_id: int) -> list[dict[str, Any]]:
        with self._read() as conn:
            self._require_active(conn, admin_id, "ADMIN")
            rows = conn.execute(
                "SELECT user_id,full_name,email,phone_num,role,status,balance_cents FROM users ORDER BY user_id"
            ).fetchall()
            return self._records(rows)

    def admin_edit_user(self, admin_id: int, target_id: int, name: str = "", phone: str = "") -> None:
        name, phone = (name or "").strip(), (phone or "").strip()
        if not (name or phone):
            raise ZimiFareError("Enter a new name or phone number.")
        if name:
            name = require_text(name, "Name")
        if phone:
            phone = require_text(phone, "Phone", 40)
        with self._write() as conn:
            self._require_active(conn, admin_id, "ADMIN")
            row = conn.execute("SELECT * FROM users WHERE user_id=?", (target_id,)).fetchone()
            if not row:
                raise ZimiFareError("User not found.")
            conn.execute(
                "UPDATE users SET full_name=?,phone_num=? WHERE user_id=?",
                (name or row["full_name"], phone or row["phone_num"], target_id),
            )

    def set_user_status(self, admin_id: int, target_id: int, new_status: str) -> None:
        if new_status not in ("BLOCKED", "DISABLED"):
            raise ZimiFareError("Only BLOCKED and DISABLED status changes are supported.")
        with self._write() as conn:
            self._require_active(conn, admin_id, "ADMIN")
            row = conn.execute("SELECT * FROM users WHERE user_id=?", (target_id,)).fetchone()
            if not row:
                raise ZimiFareError("User not found.")
            if row["role"] == "ADMIN":
                raise AccessDenied("Administrator accounts cannot be disabled or blocked here.")
            if row["status"] == "BLOCKED" and new_status == "DISABLED":
                raise ZimiFareError("An existing block cannot be weakened to disabled.")
            if row["status"] == new_status:
                raise ZimiFareError("The account already has this status.")
            conn.execute("UPDATE users SET status=? WHERE user_id=?", (new_status, target_id))

    def list_transactions(self, admin_id: int, *, transaction_id: int | None = None, flagged_only: bool = False) -> list[dict[str, Any]]:
        with self._read() as conn:
            self._require_active(conn, admin_id, "ADMIN")
            where, params = [], []
            if transaction_id is not None:
                where.append("t.transaction_id=?")
                params.append(transaction_id)
            if flagged_only:
                where.append("t.flagged=1")
            sql = """SELECT t.*, p.full_name AS passenger_name,
                COALESCE(d.full_name,'—') AS driver_name
                FROM transactions t JOIN users p ON p.user_id=t.passenger_id
                LEFT JOIN users d ON d.user_id=t.driver_id"""
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY t.transaction_id DESC"
            return self._records(conn.execute(sql, params).fetchall())

    def detect_fraud(self, admin_id: int) -> list[dict[str, Any]]:
        with self._write() as conn:
            self._require_active(conn, admin_id, "ADMIN")
            conn.execute(
                "UPDATE transactions SET flagged=CASE WHEN amount_cents > ? THEN 1 ELSE 0 END",
                (FRAUD_THRESHOLD_CENTS,),
            )
        return self.list_transactions(admin_id, flagged_only=True)
