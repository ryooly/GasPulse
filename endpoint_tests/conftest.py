"""Standalone, deletable pytest fixtures for verifying GasPulse endpoints.

This folder lives OUTSIDE the main package structure (a sibling of ``app/`` and
``db/``) and never imports-mutates the backend: it only reads the FastAPI app and
overrides the ``get_db`` dependency with an isolated in-memory SQLite database.
Delete the whole ``endpoint_tests/`` folder at any time to remove these tests.
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# --- make the project importable no matter where pytest is invoked from ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app.main as main  # noqa: E402
from app.models.blockchains import Blockchain  # noqa: E402
from app.models.fee_chart_models import FeeChartData  # noqa: E402
from app.models.fee_snapshot_models import FeeSnapshot, FeeStatus  # noqa: E402
from app.models.time_unit_models import TimeUnit, TimeUnitName  # noqa: E402
from db.base import Base, utcnow  # noqa: E402
from db.session import get_db  # noqa: E402

BLOCKCHAIN_NAME = "Ethereum"
INTERVALS = {
    TimeUnitName.HOUR: 3600,
    TimeUnitName.DAY: 86400,
    TimeUnitName.WEEK: 604800,
}


@pytest.fixture()
def engine():
    """A single shared in-memory SQLite connection (StaticPool).

    StaticPool is required because FastAPI runs sync endpoints in a worker
    thread; the default SQLite memory pool would hand each thread its own empty
    database.
    """
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=eng)
    try:
        yield eng
    finally:
        Base.metadata.drop_all(bind=eng)
        eng.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


@pytest.fixture()
def client(session_factory):
    """TestClient with ``get_db`` overridden to use the isolated test DB."""

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_get_db
    # Not used as a context manager on purpose: that would trigger the app's
    # lifespan (create_all on the real engine / gaspulse.db). The get_db override
    # above already routes all DB access to the isolated in-memory database.
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


@pytest.fixture()
def seed_base(session_factory) -> SimpleNamespace:
    """Seed one blockchain and the three time units; return their ids."""
    with session_factory() as db:
        eth = Blockchain(
            name=BLOCKCHAIN_NAME, symbol="ETH", native_currency="ETH",
        )
        units = {
            name: TimeUnit(name=name, interval_seconds=seconds)
            for name, seconds in INTERVALS.items()
        }
        db.add(eth)
        db.add_all(units.values())
        db.commit()
        return SimpleNamespace(
            session_factory=session_factory,
            blockchain_name=BLOCKCHAIN_NAME,
            blockchain_id=eth.id,
            unit_ids={name: unit.id for name, unit in units.items()},
        )


@pytest.fixture()
def seed_fees(seed_base) -> SimpleNamespace:
    """Seed a *fresh* fee snapshot for each timeframe (so /hour|day|week return it)."""
    now = utcnow()
    with seed_base.session_factory() as db:
        for name, unit_id in seed_base.unit_ids.items():
            db.add(FeeSnapshot(
                blockchain_id=seed_base.blockchain_id,
                time_unit_id=unit_id,
                raw_fee_value=1.5,
                usd_value=0.25,
                sample_count=3,
                status=FeeStatus.STABLE,
                recorded_at=now,
            ))
        db.commit()
    return seed_base


@pytest.fixture()
def seed_charts(seed_base) -> SimpleNamespace:
    """Seed chart points: 30 hourly, 10 daily, 5 weekly (chronological)."""
    now = utcnow()
    plan = {
        TimeUnitName.HOUR: (timedelta(hours=1), 30),
        TimeUnitName.DAY: (timedelta(days=1), 10),
        TimeUnitName.WEEK: (timedelta(weeks=1), 5),
    }
    with seed_base.session_factory() as db:
        for name, (step, count) in plan.items():
            unit_id = seed_base.unit_ids[name]
            for i in range(count):
                db.add(FeeChartData(
                    blockchain_id=seed_base.blockchain_id,
                    time_unit_id=unit_id,
                    fee_value=i + 1,
                    # oldest -> newest as i grows
                    recorded_at=now - step * (count - i),
                ))
        db.commit()
    return seed_base
