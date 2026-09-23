"""Seed the real (Docker) PostgreSQL database with fake-but-realistic rows.

The data is fabricated, but it matches each table's real structure exactly:
blockchains, time_units, fee_snapshots and fee_chart_data. Re-running is safe —
existing rows are cleared first.

Run:
    python dev-infra/seed.py
"""
from __future__ import annotations

import os
import random
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

# Point at the docker-compose Postgres BEFORE importing the app's DB session.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://gaspulse:gaspulse@127.0.0.1:5433/gaspulse",
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import delete  # noqa: E402

from app.models.blockchains import Blockchain  # noqa: E402
from app.models.fee_chart_models import FeeChartData  # noqa: E402
from app.models.fee_snapshot_models import FeeSnapshot, FeeStatus  # noqa: E402
from app.models.time_unit_models import TimeUnit, TimeUnitName  # noqa: E402
from db.base import utcnow  # noqa: E402
from db.session import SessionLocal  # noqa: E402

random.seed(1234)

# name, symbol, chain_id, native_currency, explorer_api_url, base_fee, fee_jitter
CHAINS = [
    ("Ethereum", "ETH", 1, "ETH", "https://api.etherscan.io/api", Decimal("25"), Decimal("6")),
    ("Polygon", "POL", 137, "POL", "https://api.polygonscan.com/api", Decimal("30"), Decimal("8")),
    ("Arbitrum", "ARB", 42161, "ETH", "https://api.arbiscan.io/api", Decimal("0.10"), Decimal("0.05")),
    ("BNB Smart Chain", "BNB", 56, "BNB", "https://api.bscscan.com/api", Decimal("3"), Decimal("1")),
    ("Avalanche", "AVAX", 43114, "AVAX", "https://api.snowtrace.io/api", Decimal("25"), Decimal("7")),
    ("Optimism", "OP", 10, "ETH", "https://api-optimistic.etherscan.io/api", Decimal("0.05"), Decimal("0.03")),
]

UNITS = {
    TimeUnitName.HOUR: (3600, timedelta(hours=1), 72),
    TimeUnitName.DAY: (86400, timedelta(days=1), 21),
    TimeUnitName.WEEK: (604800, timedelta(weeks=1), 9),
}

# Rough native-token -> USD prices for the fabricated usd_value column.
USD_PRICE = {
    "ETH": Decimal("2500"), "POL": Decimal("0.5"),
    "BNB": Decimal("600"), "AVAX": Decimal("30"),
}


def _q(value: Decimal, places: str = "0.000001") -> Decimal:
    return value.quantize(Decimal(places))


def _walk(base: Decimal, jitter: Decimal, steps: int) -> list[Decimal]:
    """A gentle random walk around ``base`` producing ``steps`` fee values."""
    values: list[Decimal] = []
    current = base
    for _ in range(steps):
        delta = (Decimal(str(random.random())) - Decimal("0.5")) * jitter
        current = max(Decimal("0.000001"), current + delta)
        values.append(_q(current, "0.000000000000000000"))
    return values


def _status(change_pct: Decimal | None) -> FeeStatus:
    if change_pct is None:
        return FeeStatus.STABLE
    if change_pct > Decimal("0.5"):
        return FeeStatus.UP
    if change_pct < Decimal("-0.5"):
        return FeeStatus.DOWN
    return FeeStatus.STABLE


def reset(db) -> None:
    """Clear all rows in FK-safe order so seeding is idempotent."""
    db.execute(delete(FeeChartData))
    db.execute(delete(FeeSnapshot))
    db.execute(delete(TimeUnit))
    db.execute(delete(Blockchain))
    db.commit()


def seed() -> None:
    now = utcnow()
    db = SessionLocal()
    try:
        reset(db)

        units: dict[TimeUnitName, TimeUnit] = {}
        for name, (interval, _step, _count) in UNITS.items():
            unit = TimeUnit(name=name, interval_seconds=interval)
            db.add(unit)
            units[name] = unit

        chains: list[Blockchain] = []
        for name, symbol, chain_id, currency, url, _base, _jitter in CHAINS:
            chain = Blockchain(
                name=name, symbol=symbol, chain_id=chain_id,
                native_currency=currency, explorer_api_url=url, is_active=True,
            )
            db.add(chain)
            chains.append(chain)
        db.flush()  # populate ids

        chart_rows = 0
        snapshot_rows = 0
        block_number = 20_000_000

        for chain, (_n, _s, _c, currency, _u, base, jitter) in zip(chains, CHAINS):
            for name, (_interval, step, count) in UNITS.items():
                unit = units[name]

                # --- fee_chart_data: chronological series of `count` points ---
                series = _walk(base, jitter, count)
                for i, fee in enumerate(series):
                    db.add(FeeChartData(
                        blockchain_id=chain.id,
                        time_unit_id=unit.id,
                        fee_value=fee,
                        recorded_at=now - step * (count - i),
                    ))
                    chart_rows += 1

                # --- fee_snapshots: 3 recent rows, the newest is "fresh" ---
                snap_series = _walk(base, jitter, 3)
                for age in (2, 1, 0):
                    raw = snap_series[2 - age]
                    prev = snap_series[1 - age] if age < 2 else None
                    change = (
                        None if prev is None or prev == 0
                        else _q((raw - prev) / prev * 100, "0.0001")
                    )
                    price = USD_PRICE.get(currency)
                    usd = _q(raw * price, "0.00000001") if price else None
                    db.add(FeeSnapshot(
                        blockchain_id=chain.id,
                        time_unit_id=unit.id,
                        raw_fee_value=raw,
                        usd_value=usd,
                        avg_fee=_q(raw, "0.000000000000000000"),
                        median_fee=_q(raw * Decimal("0.98"), "0.000000000000000000"),
                        min_fee=_q(raw * Decimal("0.85"), "0.000000000000000000"),
                        max_fee=_q(raw * Decimal("1.20"), "0.000000000000000000"),
                        sample_count=random.randint(50, 500),
                        previous_value=prev,
                        status=_status(change),
                        change_percentage=change,
                        block_number=block_number - age,
                        recorded_at=now - step * age,
                    ))
                    snapshot_rows += 1
                block_number += random.randint(100, 900)

        db.commit()
        print("Seed complete:")
        print(f"  blockchains    : {len(chains)}")
        print(f"  time_units     : {len(units)}")
        print(f"  fee_snapshots  : {snapshot_rows}")
        print(f"  fee_chart_data : {chart_rows}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
