"""Regression tests covering structured references, analytics, and admin access."""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from zimifare.analytics import filter_transactions, summarise_transactions
from zimifare.core import AccessDenied, ZimiFareStore
from zimifare.identifiers import (
    user_ref, ride_ref, transaction_ref, parse_transaction_ref
)


class ReferenceTests(unittest.TestCase):
    def test_public_ids_are_structured_and_stable(self):
        self.assertEqual(user_ref(1, "ADMIN"), "ZF-ADM-000001")
        self.assertEqual(user_ref(2, "PASSENGER"), "ZF-PSG-000002")
        self.assertEqual(user_ref(3, "DRIVER"), "ZF-DRV-000003")
        self.assertEqual(ride_ref(42), "ZF-RID-000042")
        self.assertEqual(transaction_ref(15001), "ZF-TXN-015001")

    def test_transaction_search_accepts_old_ids(self):
        for value in ("zf-txn-000011", "TX-00011", "11", 11):
            self.assertEqual(parse_transaction_ref(value), 11)
        for bad in ("", "ZF-RID-000011", "ZF-PSG-000011", "TX-0", "12A", "-1"):
            with self.assertRaises(ValueError):
                parse_transaction_ref(bad)

    def test_invalid_user_role(self):
        with self.assertRaises(ValueError):
            user_ref(3, "INVALID")


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ZimiFareStore(Path(self.temp.name) / "zimifare.db")
        self.admin = self.store.bootstrap_admin("Admin", "admin@zimifare.test", "1", "Adminsecret123", trusted_setup=True)
        self.p = self.store.register("Passenger", "p@zimifare.test", "2", "PassengerSecret123", "PASSENGER")
        self.d = self.store.register("Driver", "d@zimifare.test", "3", "DriverSecret123", "DRIVER")

    def test_analytics_separates_topups_and_fares(self):
        self.store.top_up(self.p, 100_000)
        ride_one = self.store.create_ride(self.d, self.p, "2026-11-11", "A", "B", 30_000)
        self.store.settle_ride(self.p, ride_one, "FARE_CARD")
        ride_two = self.store.create_ride(self.d, self.p, "2026-11-11", "A", "C", 50_000)
        self.store.settle_ride(self.d, ride_two, "CASH")
        rows = self.store.list_transactions(self.admin)
        summary = summarise_transactions(rows)
        self.assertEqual(summary["transactions"], 3)
        self.assertEqual(summary["topup_cents"], 100_000)
        self.assertEqual(summary["fare_cents"], 80_000)
        self.assertEqual(summary["card_cents"], 30_000)
        self.assertEqual(summary["cash_cents"], 50_000)
        self.assertEqual(summary["flagged_count"], 0)
        self.assertEqual(sum(r["amount"] for r in summary["daily"]), 1800.0)
        only_fares = filter_transactions(rows, types={"FARE_PAYMENT"})
        self.assertEqual(len(only_fares), 2)
        self.assertEqual(len(filter_transactions(rows, methods={"CASH"})), 1)
        self.assertEqual(len(filter_transactions(rows, start=date(2099,1,1))), 0)
        self.assertEqual(len(filter_transactions(rows, end=date(1999,12,31))), 0)
        self.assertEqual(len(filter_transactions(rows, keyword="Passenger")), 3)
        self.assertEqual(len(filter_transactions(rows, keyword="ZF-TXN-000001")), 1)
        self.assertEqual(len(filter_transactions(rows, keyword="ZF-RID-000001")), 1)
        self.assertEqual(len(filter_transactions(rows, flagged=True)), 0)

    def test_reports_show_actual_transaction_flags(self):
        self.store.top_up(self.p, 5_000_000)
        self.store.top_up(self.p, 5_000_001)
        summary = summarise_transactions(self.store.list_transactions(self.admin))
        self.assertEqual(summary["flagged_count"], 1)
        self.assertEqual(summary["fare_cents"], 0)
        self.assertEqual(summary["topup_cents"], 10_000_001)

    def test_admin_can_read_all_rides_passenger_cannot(self):
        ride = self.store.create_ride(self.d, self.p, "2026-11-11", "Kingston", "Airport", 7000)
        rows = self.store.admin_list_rides(self.admin)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ride_id"], ride)
        self.assertEqual(rows[0]["driver_name"], "Driver")
        with self.assertRaises(AccessDenied):
            self.store.admin_list_rides(self.p)
        with self.assertRaises(AccessDenied):
            self.store.admin_list_rides(self.d)

    def test_existing_numbers_remain_the_primary_keys(self):
        self.assertEqual(self.p, 2)
        self.assertEqual(self.d, 3)
        self.assertEqual(self.store.login("p@zimifare.test", "PassengerSecret123")["user_id"], 2)
        self.assertEqual(user_ref(self.store.current_user(self.d)["user_id"], "DRIVER"), "ZF-DRV-000003")

if __name__ == '__main__':
    unittest.main()
