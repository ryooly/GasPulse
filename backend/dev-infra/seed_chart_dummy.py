from __future__ import annotations

import math
import os
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import delete, select

# Import all models so Base.metadata knows every table.
from app.models.blockchains import Blockchain  # noqa: F401
from app.models.fee_chart_models import FeeChartData  # noqa: F401
from app.models.fee_snapshot_models import FeeSnapshot  # noqa: F401
from app.models.time_unit_models import TimeUnit, TimeUnitName  # noqa: F401
from db.base import Base, utcnow
from db.session import SessionLocal, engine

CHAIN_SPECS = [
    ("Bitcoin", "BTC", None, "BTC", 12.0),
    ("Ethereum", "ETH", 1, "ETH", 18.0),
    ("Solana", "SOL", None, "SOL", 0.01),
    ("BNB Chain", "BNB", 56, "BNB", 3.0),
    ("Avalanche", "AVAX", 43114, "AVAX", 25.0),
    ("Polygon", "POL", 137, "POL", 42.0),
    ("Chainlink", "LINK", 1, "ETH", 15.0),
    ("Polkadot", "DOT", None, "DOT", 0.05),
]

UNITS = {
    TimeUnitName.HOUR: (3600, timedelta(hours=1), 72),
    TimeUnitName.DAY: (86400, timedelta(days=1), 21),
    TimeUnitName.WEEK: (604800, timedelta(weeks=1), 9),
}


def q(v: float) -> Decimal:
    return Decimal(str(round(v, 12)))


def series(base: float, count: int, phase: float) -> list[Decimal]:
    vals: list[Decimal] = []
    for i in range(count):
        wave = math.sin((i / max(1, count - 1)) * math.pi * 2 + phase)
        drift = (i / max(1, count - 1) - 0.5) * 0.12
        val = base * (1.0 + 0.18 * wave + drift)
        vals.append(q(max(val, base * 0.05)))
    return vals


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    now = utcnow()
    db = SessionLocal()
    try:
        unit_rows: dict[TimeUnitName, TimeUnit] = {}
        for name, (interval, _step, _count) in UNITS.items():
            unit = db.scalar(select(TimeUnit).where(TimeUnit.name == name))
            if unit is None:
                unit = TimeUnit(name=name, interval_seconds=interval)
                db.add(unit)
                db.flush()
            unit_rows[name] = unit

        inserted = 0
        for idx, (name, symbol, chain_id, currency, base) in enumerate(CHAIN_SPECS):
            chain = db.scalar(select(Blockchain).where(Blockchain.name == name))
            if chain is None:
                chain = Blockchain(
                    name=name,
                    symbol=symbol,
                    chain_id=chain_id,
                    native_currency=currency,
                    explorer_api_url=None,
                    is_active=True,
                )
                db.add(chain)
                db.flush()

            db.execute(delete(FeeChartData).where(FeeChartData.blockchain_id == chain.id))

            for uname, (_interval, step, count) in UNITS.items():
                unit = unit_rows[uname]
                vals = series(base, count, phase=idx * 0.7 + (0.2 if uname == TimeUnitName.DAY else 0.4 if uname == TimeUnitName.WEEK else 0.0))
                for i, fee in enumerate(vals):
                    db.add(FeeChartData(
                        blockchain_id=chain.id,
                        time_unit_id=unit.id,
                        fee_value=fee,
                        recorded_at=now - step * (count - i),
                    ))
                    inserted += 1

        db.commit()
        print("Dummy chart seed complete")
        print(f"  chains: {len(CHAIN_SPECS)}")
        print(f"  fee_chart_data inserted: {inserted}")
        print(f"  time units: hour(72), day(21), week(9)")
        print(f"  database_url: {os.getenv('DATABASE_URL', 'sqlite:///./gaspulse.db')}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
