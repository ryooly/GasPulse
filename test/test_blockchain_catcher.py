from __future__ import annotations

"""Integration test for blockchain_catcher using real Docker PostgreSQL.

Prerequisites:
    1. Start Docker:  docker compose -f dev-infra/docker-compose.yml up -d
    2. Install deps:  pip install -r dev-infra/requirements.txt

Run:
    python -m pytest test/test_blockchain_catcher.py -v

Validate real DB rows after the run (tables + data kept):
    $env:KEEP_DB="1"; python -m pytest test/test_blockchain_catcher.py -v -s
    docker exec gaspulse-db psql -U gaspulse -d gaspulse_test -c "SELECT * FROM fee_snapshots;"
    $env:KEEP_DB=""   # next run will clean up again
"""

import os
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.blockchains import Blockchain
from app.models.fee_snapshot_models import FeeSnapshot, FeeStatus
from app.models.time_unit_models import TimeUnit, TimeUnitName
from app.modules.automation.blockchain_catcher import (
    BaseBlockchainCatcher,
    CapturedBlock,
    EtherscanCatcher,
    ScannerAPIError,
)
from db.base import Base

# ─── Docker PostgreSQL connection ───────────────────────────────────────────

TEST_DB_NAME = "gaspulse_test"
ADMIN_DATABASE_URL = "postgresql+psycopg://gaspulse:gaspulse@127.0.0.1:5433/gaspulse"
TEST_DATABASE_URL = f"postgresql+psycopg://gaspulse:gaspulse@127.0.0.1:5433/{TEST_DB_NAME}"


@pytest.fixture(scope="module")
def engine():
    """Ensure the test database exists on Docker Postgres, then build schema once."""
    from sqlalchemy import text

    # Connect to the default 'gaspulse' db and create 'gaspulse_test' if missing.
    admin_engine = create_engine(ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT", future=True)
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db"), {"db": TEST_DB_NAME}
        ).fetchone()
        if exists is None:
            conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    admin_engine.dispose()

    eng = create_engine(TEST_DATABASE_URL, future=True)
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    yield eng
    if os.getenv("KEEP_DB") == "1":
        print(f"\n[KEEP_DB=1] schema left intact at {TEST_DATABASE_URL}")
    else:
        Base.metadata.drop_all(bind=eng)
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    """Fresh schema per test so committed rows from one test never leak into the next.

    Note: KEEP_DB only preserves the schema produced by the LAST test in the run.
    To inspect a specific test's data, filter to just that test, e.g.:
        $env:KEEP_DB="1"; python -m pytest test/test_blockchain_catcher.py -k test_capture_twice -s
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _mock_http_layer(catcher: BaseBlockchainCatcher, base_fee_wei: int = 25_000_000_000):
    """Patch catcher's HTTP session to return deterministic block data."""
    mock_session = MagicMock()

    def mock_get(url, params=None, headers=None, timeout=None):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.status_code = 200
        action = params.get("action")

        if action == "getblocknobytime":
            resp.json.return_value = {"status": "1", "message": "OK", "result": "19000000"}
        elif action == "eth_blockNumber":
            resp.json.return_value = {"jsonrpc": "2.0", "result": hex(19000000)}
        elif action == "eth_getBlockByNumber":
            tag = params.get("tag", hex(19000000))
            block_num = int(tag, 16) if isinstance(tag, str) else tag
            resp.json.return_value = {
                "jsonrpc": "2.0",
                "result": {
                    "number": hex(block_num),
                    "timestamp": hex(1700000000 + block_num),
                    "baseFeePerGas": hex(base_fee_wei),
                    "gasUsed": "0x1c9c38",
                    "gasLimit": "0x1c9c380",
                },
            }
        elif action == "gasoracle":
            resp.json.return_value = {
                "status": "1",
                "message": "OK",
                "result": {
                    "SafeGasPrice": "20",
                    "ProposeGasPrice": "25",
                    "FastGasPrice": "30",
                    "suggestBaseFee": "22.5",
                },
            }
        else:
            resp.json.return_value = {"status": "1", "result": {}}
        return resp

    mock_session.get.side_effect = mock_get
    catcher.session = mock_session


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestCaptureAndInsertWithRealDB:
    """End-to-end test: catcher fetches blocks (mocked HTTP) and inserts into real PostgreSQL."""

    def test_capture_and_insert_creates_snapshot(self, db_session: Session):
        """Full flow: resolve timeframe -> fetch blocks -> compute metrics -> insert snapshot."""
        catcher = EtherscanCatcher()
        _mock_http_layer(catcher, base_fee_wei=30_000_000_000)  # 30 Gwei

        snapshot = catcher.capture_and_insert(
            db=db_session,
            timeframe="hour",
            sample_size=1,
        )

        # Verify persisted to real DB
        assert snapshot.id is not None
        assert snapshot.raw_fee_value == Decimal("30.000000000000000000")
        assert snapshot.block_number == 19000000
        assert snapshot.status == FeeStatus.STABLE
        assert snapshot.sample_count == 1

        # Verify relationships resolved from DB
        assert snapshot.blockchain.name == "Ethereum"
        assert snapshot.blockchain.symbol == "ETH"
        assert snapshot.time_unit.name == TimeUnitName.HOUR

        # Confirm row exists in database
        row = db_session.scalars(
            select(FeeSnapshot).where(FeeSnapshot.id == snapshot.id)
        ).first()
        assert row is not None
        assert row.raw_fee_value == Decimal("30.000000000000000000")

        # Print DB evidence (visible with `pytest -s`)
        print(
            f"\n[DB] fee_snapshots row -> id={row.id} "
            f"blockchain={row.blockchain.name} time_unit={row.time_unit.name.value} "
            f"raw_fee={row.raw_fee_value} status={row.status.value} "
            f"block_number={row.block_number}"
        )

    def test_capture_twice_computes_change_percentage(self, db_session: Session):
        """Second capture should compare against the first snapshot in DB."""
        catcher = EtherscanCatcher()

        # First capture at 20 Gwei
        _mock_http_layer(catcher, base_fee_wei=20_000_000_000)
        snap1 = catcher.capture_and_insert(db=db_session, timeframe="hour", sample_size=1)
        assert snap1.previous_value is None
        assert snap1.change_percentage is None
        assert snap1.status == FeeStatus.STABLE

        # Second capture at 35 Gwei -> should detect +75% change
        _mock_http_layer(catcher, base_fee_wei=35_000_000_000)
        snap2 = catcher.capture_and_insert(db=db_session, timeframe="hour", sample_size=1)
        assert snap2.previous_value == Decimal("20.000000000000000000")
        assert snap2.change_percentage == Decimal("75.0000")
        assert snap2.status == FeeStatus.UP

        # Both rows exist in DB
        rows = db_session.scalars(
            select(FeeSnapshot).order_by(FeeSnapshot.id.asc())
        ).all()
        assert len(rows) == 2

    def test_blockchain_and_time_unit_created_automatically(self, db_session: Session):
        """Verify _get_or_create logic works against real DB constraints."""
        catcher = EtherscanCatcher()
        _mock_http_layer(catcher, base_fee_wei=25_000_000_000)

        # Call twice — should reuse same blockchain and time_unit
        snap1 = catcher.capture_and_insert(db=db_session, timeframe="hour", sample_size=1)
        snap2 = catcher.capture_and_insert(db=db_session, timeframe="hour", sample_size=1)

        assert snap1.blockchain_id == snap2.blockchain_id
        assert snap1.time_unit_id == snap2.time_unit_id

        # Only one blockchain and one time_unit row
        chains = db_session.scalars(select(Blockchain)).all()
        units = db_session.scalars(select(TimeUnit)).all()
        assert len(chains) == 1
        assert len(units) == 1
        assert chains[0].name == "Ethereum"
        assert units[0].name == TimeUnitName.HOUR

    def test_fetch_blocks_returns_expected_output(self, db_session: Session):
        """Verify the block-fetching pipeline returns correct CapturedBlock data."""
        catcher = EtherscanCatcher()

        # Mock with a range: start=100, end=104, sample 3 blocks
        mock_session = MagicMock()

        def mock_get(url, params=None, headers=None, timeout=None):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            resp.status_code = 200
            action = params.get("action")

            if action == "getblocknobytime":
                resp.json.return_value = {"status": "1", "message": "OK", "result": "100"}
            elif action == "eth_blockNumber":
                resp.json.return_value = {"jsonrpc": "2.0", "result": "0x68"}  # 104
            elif action == "eth_getBlockByNumber":
                tag = params.get("tag", "0x68")
                block_num = int(tag, 16)
                resp.json.return_value = {
                    "jsonrpc": "2.0",
                    "result": {
                        "number": hex(block_num),
                        "timestamp": hex(1700000000 + block_num),
                        "baseFeePerGas": hex((block_num + 1) * 10**9),
                        "gasUsed": "0x1c9c38",
                        "gasLimit": "0x1c9c380",
                    },
                }
            else:
                resp.json.return_value = {"status": "1", "result": {}}
            return resp

        mock_session.get.side_effect = mock_get
        catcher.session = mock_session

        blocks = catcher.fetch_blocks_by_time_range(seconds=3600, sample_size=3)

        assert len(blocks) == 3
        assert all(isinstance(b, CapturedBlock) for b in blocks)
        numbers = [b.number for b in blocks]
        assert numbers == sorted(numbers)
        assert numbers[0] == 100
        assert numbers[-1] == 104
        # fee = (block_num + 1) Gwei
        for b in blocks:
            assert b.fee_gwei == Decimal(b.number + 1)

    def test_scanner_error_raises_exception(self, db_session: Session):
        """Verify network errors propagate as ScannerAPIError."""
        import requests

        catcher = EtherscanCatcher()
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.RequestException("Connection refused")
        catcher.session = mock_session

        with pytest.raises(ScannerAPIError, match="HTTP request to .* failed"):
            catcher.get_latest_block_number()
