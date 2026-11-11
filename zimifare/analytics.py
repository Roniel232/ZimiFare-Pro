"""Accurate summaries over recorded ZimiFare transactions (no demo/mock data)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from .identifiers import ride_ref, transaction_ref


def filter_transactions(rows: list[dict[str, Any]], *, start: date | None = None,
                        end: date | None = None, types: set[str] | None = None,
                        methods: set[str] | None = None, flagged: bool = False,
                        keyword: str = "") -> list[dict[str, Any]]:
    """Use UTC transaction timestamps for date range comparisons."""
    needle = keyword.casefold().strip()
    out = []
    for r in rows:
        # UTC ISO date portion is YYYY-MM-DD.
        day = date.fromisoformat(r["recorded_at"][:10])
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        if types is not None and r["tx_type"] not in types:
            continue
        if methods is not None and r["method"] not in methods:
            continue
        if flagged and not r["flagged"]:
            continue
        if needle and needle not in " ".join((
            str(r.get("transaction_id", "")),
            transaction_ref(r["transaction_id"]),
            str(r.get("ride_id", "")),
            ride_ref(r["ride_id"]) if r.get("ride_id") else "",
            r.get("passenger_name", ""), r.get("driver_name", ""),
            r["tx_type"], r["method"],
        )).casefold():
            continue
        out.append(r)
    return out


def summarise_transactions(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Separate simulated top-ups from paid fare revenue to avoid double counting."""
    daily: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"count": 0, "amount_cents": 0})
    method_totals: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "amount_cents": 0})
    topup_cents = fare_cents = cash_cents = card_cents = 0
    flagged_count = 0
    for r in rows:
        cents = int(r["amount_cents"])
        typ = r["tx_type"]
        date_str = r["recorded_at"][:10]
        daily[(date_str, typ)]["count"] += 1
        daily[(date_str, typ)]["amount_cents"] += cents
        method_totals[r["method"]]["count"] += 1
        method_totals[r["method"]]["amount_cents"] += cents
        flagged_count += bool(r["flagged"])
        if typ == "TOP_UP":
            topup_cents += cents
        elif typ == "FARE_PAYMENT":
            fare_cents += cents
            if r["method"] == "CASH":
                cash_cents += cents
            elif r["method"] == "FARE_CARD":
                card_cents += cents
    return {
        "transactions": len(rows),
        "topup_cents": topup_cents,
        "fare_cents": fare_cents,
        "cash_cents": cash_cents,
        "card_cents": card_cents,
        "flagged_count": flagged_count,
        "daily": [
            {"day": day, "type": typ, "count": val["count"], "amount": val["amount_cents"] / 100}
            for (day, typ), val in sorted(daily.items())
        ],
        "by_method": [
            {"method": method, "count": vals["count"], "amount": vals["amount_cents"] / 100}
            for method, vals in sorted(method_totals.items())
        ],
    }
