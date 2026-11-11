"""Stable, presentation-safe public references for internal SQLite integer IDs.

IDs are NOT renumbered or migrated. A role-specific prefix makes old records
and new ones easy to identify without breaking existing foreign keys.
"""
from __future__ import annotations

import re

_ROLE_CODES = {"PASSENGER": "PSG", "DRIVER": "DRV", "ADMIN": "ADM"}


def user_ref(user_id: int, role: str) -> str:
    code = _ROLE_CODES.get(str(role).upper())
    if code is None or int(user_id) <= 0:
        raise ValueError("Invalid user role or ID")
    return f"ZF-{code}-{int(user_id):06d}"


def ride_ref(ride_id: int) -> str:
    if int(ride_id) <= 0:
        raise ValueError("Invalid ride ID")
    return f"ZF-RID-{int(ride_id):06d}"


def transaction_ref(transaction_id: int) -> str:
    if int(transaction_id) <= 0:
        raise ValueError("Invalid transaction ID")
    return f"ZF-TXN-{int(transaction_id):06d}"


def parse_transaction_ref(text: str | int) -> int:
    """Accept new reference or previous numeric / TX-00001 references."""
    raw = str(text).strip().upper()
    match = re.fullmatch(r"(?:ZF-TXN-|TX-)?(\d{1,10})", raw)
    if not match or int(match.group(1)) <= 0:
        raise ValueError("Enter a valid transaction reference, e.g. ZF-TXN-000001.")
    return int(match.group(1))
