"""Regression tests for the payment, account, and fraud rules in the pseudocode.

Run: python -m unittest discover -s tests -v
"""
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from zimifare.core import (
    AccessDenied, FRAUD_THRESHOLD_CENTS, ZimiFareError, ZimiFareStore,
    cents_from_input, money,
)


class ZimiFareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ZimiFareStore(Path(self.temp.name) / "test.db")
        self.admin = self.store.bootstrap_admin(
            "System Admin", "admin@example.com", "876-000-0000", "AdminPass123!", trusted_setup=True
        )
        self.passenger = self.store.register(
            "Alicia Grant", "Alicia@EXAMPLE.com", "876-111-1111", "Passenger123!", "PASSENGER"
        )
        self.driver = self.store.register(
            "Michael Reid", "michael@example.com", "876-222-2222", "DriverPass123!", "DRIVER"
        )

    def ride(self, fare=25_000):
        return self.store.create_ride(self.driver, self.passenger, "2026-11-11", "Half Way Tree", "New Kingston", fare)

    def test_admin_is_trusted_setup_only(self):
        with self.assertRaises(AccessDenied):
            self.store.bootstrap_admin("Bad", "x@y.com", "123", "Secure123")
        with self.assertRaises(ZimiFareError):
            self.store.bootstrap_admin("Bad", "x@y.com", "123", "Secure123", trusted_setup=True)

    def test_existing_admin_can_securely_add_more_admins(self):
        second = self.store.create_administrator(
            self.admin, "AdminPass123!", "Second Admin", "second@example.com", "876-333-3333", "SecondAdmin123!"
        )
        third = self.store.create_administrator(
            second, "SecondAdmin123!", "Third Admin", "third@example.com", "876-444-4444", "ThirdAdmin123!"
        )
        self.assertEqual(self.store.login("second@example.com", "SecondAdmin123!")["role"], "ADMIN")
        self.assertEqual(self.store.login("third@example.com", "ThirdAdmin123!")["role"], "ADMIN")
        self.assertIn(third, [u["user_id"] for u in self.store.list_users(second)])

    def test_only_authorised_admin_can_add_admins(self):
        with self.assertRaises(AccessDenied):
            self.store.create_administrator(
                self.passenger, "Passenger123!", "Untrusted", "bad@example.com", "123", "Anotherpass123!"
            )
        with self.assertRaises(AccessDenied):
            self.store.create_administrator(
                self.admin, "WrongAdminPass", "Untrusted", "bad@example.com", "123", "Anotherpass123!"
            )
        self.assertFalse(any(u["email"] == "bad@example.com" for u in self.store.list_users(self.admin)))

    def test_admin_creation_rejects_duplicate_email_and_weak_password(self):
        with self.assertRaisesRegex(ZimiFareError, "already registered"):
            self.store.create_administrator(
                self.admin, "AdminPass123!", "Duplicated", "ALICIA@example.com", "123", "Anotherpass123!"
            )
        with self.assertRaisesRegex(ZimiFareError, "8 characters"):
            self.store.create_administrator(
                self.admin, "AdminPass123!", "Weak", "weak@example.com", "123", "short"
            )

    def test_email_normalization_and_duplicate_rejected(self):
        user = self.store.login("  ALICIA@EXAMPLE.COM ", "Passenger123!")
        self.assertEqual(user["user_id"], self.passenger)
        self.assertNotIn("password_hash", user)
        with self.assertRaisesRegex(ZimiFareError, "already registered"):
            self.store.register("Alicia Two", " ALICIA@example.com ", "123456", "SafePass123", "PASSENGER")

    def test_password_not_plaintext_and_role_restriction(self):
        with sqlite3.connect(self.store.db_path) as conn:
            stored = conn.execute("SELECT password_hash FROM users WHERE user_id=?", (self.passenger,)).fetchone()[0]
        self.assertNotEqual(stored, "Passenger123!")
        self.assertTrue(stored.startswith("pbkdf2_sha256$"))
        with self.assertRaises(ZimiFareError):
            self.store.login("alicia@example.com", "wrong password")
        with self.assertRaises(ZimiFareError):
            self.store.register("Not an admin", "fake@example.com", "123", "AdminPass123", "ADMIN")

    def test_decimal_money_exactness(self):
        self.assertEqual(cents_from_input("250.01"), 25001)
        self.assertEqual(money(25001), "JMD 250.01")
        for bad in ["0", "-5", "3.999", "NaN", "Infinity", "twenty"]:
            with self.assertRaises(ZimiFareError):
                cents_from_input(bad)

    def test_integrated_card_payment(self):
        top_tx, new_balance = self.store.top_up(self.passenger, 100_000)
        self.assertEqual((top_tx, new_balance), (1, 100_000))
        ride = self.ride()
        tx, remaining = self.store.settle_ride(self.passenger, ride, "FARE_CARD")
        self.assertEqual((tx, remaining), (2, 75_000))
        self.assertEqual(self.store.current_user(self.passenger)["balance_cents"], 75_000)
        self.assertEqual(self.store.get_ride(self.passenger, ride)["payment_status"], "PAID")
        self.assertEqual(self.store.get_ride(self.passenger, ride)["transaction_id"], tx)
        self.assertEqual(self.store.driver_earnings(self.driver)["total_cents"], 25_000)
        self.assertEqual(len(self.store.list_transactions(self.admin)), 2)

    def test_duplicate_payment_not_possible(self):
        self.store.top_up(self.passenger, 100_000)
        ride = self.ride()
        self.store.settle_ride(self.passenger, ride, "FARE_CARD")
        with self.assertRaisesRegex(ZimiFareError, "already been paid"):
            self.store.settle_ride(self.driver, ride, "CASH")
        self.assertEqual(len(self.store.list_transactions(self.admin)), 2)
        self.assertEqual(self.store.current_user(self.passenger)["balance_cents"], 75_000)

    def test_insufficient_funds_has_zero_side_effects(self):
        ride = self.ride()
        with self.assertRaisesRegex(ZimiFareError, "Insufficient"):
            self.store.settle_ride(self.passenger, ride, "FARE_CARD")
        self.assertEqual(self.store.get_ride(self.passenger, ride)["payment_status"], "UNPAID")
        self.assertEqual(len(self.store.list_transactions(self.admin)), 0)

    def test_cash_payment_does_not_debit_card(self):
        self.store.top_up(self.passenger, 10_000)
        ride = self.ride(40_000)
        tx, balance = self.store.settle_ride(self.driver, ride, "CASH")
        self.assertIsNone(balance)
        self.assertEqual(self.store.current_user(self.passenger)["balance_cents"], 10_000)
        self.assertEqual(self.store.get_ride(self.passenger, ride)["payment_method"], "CASH")
        self.assertEqual(self.store.driver_earnings(self.driver)["total_cents"], 40_000)

    def test_access_control_and_ride_ownership(self):
        second = self.store.register("Other Passenger", "other@example.com", "123", "Otherpass123", "PASSENGER")
        self.store.top_up(second, 100_000)
        ride = self.ride()
        with self.assertRaises(AccessDenied):
            self.store.settle_ride(second, ride, "FARE_CARD")
        with self.assertRaises(AccessDenied):
            self.store.settle_ride(self.passenger, ride, "CASH")
        with self.assertRaises(AccessDenied):
            self.store.list_users(self.passenger)
        with self.assertRaises(AccessDenied):
            self.store.passengers(self.passenger)

    def test_inactive_participant_prevents_settlement(self):
        ride = self.ride()
        self.store.set_user_status(self.admin, self.passenger, "DISABLED")
        with self.assertRaises(AccessDenied):
            self.store.login("alicia@example.com", "Passenger123!")
        with self.assertRaises(AccessDenied):
            self.store.settle_ride(self.driver, ride, "CASH")
        self.assertEqual(self.store.get_ride(self.driver, ride)["payment_status"], "UNPAID")

    def test_admin_user_restrictions_and_history_preserved(self):
        ride = self.ride()
        self.store.set_user_status(self.admin, self.driver, "BLOCKED")
        with self.assertRaises(ZimiFareError):
            self.store.set_user_status(self.admin, self.driver, "DISABLED")
        with self.assertRaises(AccessDenied):
            self.store.set_user_status(self.admin, self.admin, "BLOCKED")
        # Direct administration can see historical rides and the status is preserved.
        self.assertEqual(self.store.current_user(self.driver)["status"], "BLOCKED")
        self.assertEqual(self.store.current_user(self.driver)["user_id"], self.driver)
        self.assertEqual(ride, 1)

    def test_fraud_threshold_is_strictly_greater(self):
        self.store.top_up(self.passenger, FRAUD_THRESHOLD_CENTS)
        self.store.top_up(self.passenger, FRAUD_THRESHOLD_CENTS + 1)
        initial = self.store.list_transactions(self.admin)
        self.assertEqual({x["transaction_id"] for x in initial if x["flagged"]}, {2})
        flagged = self.store.detect_fraud(self.admin)
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]["amount_cents"], FRAUD_THRESHOLD_CENTS+1)
        self.assertEqual(self.store.current_user(self.passenger)["status"], "ACTIVE")

    def test_profile_updates_and_password_changes(self):
        self.store.update_profile(self.passenger, name="Alicia Brown", phone="876-999-9999")
        self.assertEqual(self.store.current_user(self.passenger)["full_name"], "Alicia Brown")
        with self.assertRaises(ZimiFareError):
            self.store.update_profile(self.passenger, new_password="NewPassword!", current_password="wrong")
        self.store.update_profile(self.passenger, new_password="NewPassword!", current_password="Passenger123!")
        self.assertEqual(self.store.login("alicia@example.com", "NewPassword!")["full_name"], "Alicia Brown")
        with self.assertRaises(ZimiFareError):
            self.store.login("alicia@example.com", "Passenger123!")

    def test_invalid_ride_date_is_rejected(self):
        for ride_date in ["2026-02-30", "11/11/2026", "20261111"]:
            with self.assertRaises(ZimiFareError):
                self.store.create_ride(self.driver, self.passenger, ride_date, "A", "B", 1000)

    def test_concurrent_settlement_one_winner(self):
        self.store.top_up(self.passenger, 100_000)
        ride = self.ride()
        barrier = threading.Barrier(2)
        results = []
        lock = threading.Lock()
        def worker(actor, method):
            barrier.wait()
            try:
                result = ("success", self.store.settle_ride(actor, ride, method))
            except ZimiFareError as exc:
                result = ("denied", str(exc))
            with lock:
                results.append(result)
        a = threading.Thread(target=worker, args=(self.passenger,"FARE_CARD"))
        b = threading.Thread(target=worker, args=(self.driver,"CASH"))
        a.start(); b.start(); a.join(timeout=6); b.join(timeout=6)
        self.assertEqual(len(results), 2)
        self.assertEqual(sum(r[0] == "success" for r in results), 1)
        self.assertEqual(len(self.store.list_transactions(self.admin)), 2) # top-up + 1 fare
        self.assertEqual(self.store.get_ride(self.passenger, ride)["payment_status"], "PAID")


if __name__ == "__main__":
    unittest.main()
