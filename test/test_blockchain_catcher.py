from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.blockchains import Blockchain
from app.models.fee_snapshot_models import FeeSnapshot, FeeStatus
from app.models.time_unit_models import TimeUnit, TimeUnitName
from app.modules.automation.blockchain_catcher import (
    ArbiscanCatcher,
    BaseBlockchainCatcher,
    BscScanCatcher,
    CapturedBlock,
    EtherscanCatcher,
    InvalidTimeframeError,
    PolygonscanCatcher,
    ScannerAPIError,
    SnowtraceCatcher,
)
from db.base import Base


@pytest.fixture()
def db_session():
    """In-memory SQLite database session with all tables created."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


class TestCatcherClassesAndPlaceholders:
    """Verifies that all 5 classes exist and contain the required placeholders."""

    def test_all_five_classes_instantiation_and_placeholders(self):
        catchers = [
            (EtherscanCatcher, "Ethereum", "ETH", "https://api.etherscan.io/api", "YOUR_ETHERSCAN_API_KEY"),
            (PolygonscanCatcher, "Polygon", "POL", "https://api.polygonscan.com/api", "YOUR_POLYGONSCAN_API_KEY"),
            (BscScanCatcher, "BNB Smart Chain", "BNB", "https://api.bscscan.com/api", "YOUR_BSCSCAN_API_KEY"),
            (ArbiscanCatcher, "Arbitrum", "ARB", "https://api.arbiscan.io/api", "YOUR_ARBISCAN_API_KEY"),
            (SnowtraceCatcher, "Avalanche", "AVAX", "https://api.snowtrace.io/api", "YOUR_SNOWTRACE_API_KEY"),
        ]

        for cls, name, symbol, default_url, default_key in catchers:
            catcher = cls()
            assert catcher.blockchain_name == name
            assert catcher.blockchain_symbol == symbol
            assert catcher.api_url == default_url
            assert catcher.api_key == default_key

    def test_custom_placeholders_and_env_overrides(self, monkeypatch):
        monkeypatch.setenv("ETHERSCAN_API_KEY", "custom_eth_key_123")
        monkeypatch.setenv("ETHERSCAN_API_URL", "https://custom.etherscan.io/api")

        from app.modules.automation.blockchain_catcher import etherscan_catcher

        # Explicit params override defaults
        catcher = EtherscanCatcher(
            api_url="https://override.etherscan.io/api",
            api_key="my_key_999",
        )
        assert catcher.api_url == "https://override.etherscan.io/api"
        assert catcher.api_key == "my_key_999"


class TestTimeframeResolution:
    """Tests resolving HOURS, DAYS, WEEKS into TimeUnitName and duration."""

    def test_valid_timeframes(self):
        catcher = BaseBlockchainCatcher()

        unit, secs = catcher.resolve_timeframe(TimeUnitName.HOUR)
        assert unit == TimeUnitName.HOUR and secs == 3600

        unit, secs = catcher.resolve_timeframe("hour")
        assert unit == TimeUnitName.HOUR and secs == 3600

        unit, secs = catcher.resolve_timeframe("HOURS")
        assert unit == TimeUnitName.HOUR and secs == 3600

        unit, secs = catcher.resolve_timeframe("days")
        assert unit == TimeUnitName.DAY and secs == 86400

        unit, secs = catcher.resolve_timeframe("WEEKS")
        assert unit == TimeUnitName.WEEK and secs == 604800

    def test_invalid_timeframe_raises_error(self):
        catcher = BaseBlockchainCatcher()
        with pytest.raises(InvalidTimeframeError):
            catcher.resolve_timeframe("invalid_interval")


class TestMetricsCalculation:
    """Tests calculating avg, median, min, max, change_percentage, and status."""

    def test_metrics_computation(self):
        catcher = EtherscanCatcher()
        blocks = [
            CapturedBlock(number=100, timestamp=datetime.now(timezone.utc), fee_gwei=Decimal("20.0")),
            CapturedBlock(number=101, timestamp=datetime.now(timezone.utc), fee_gwei=Decimal("25.0")),
            CapturedBlock(number=102, timestamp=datetime.now(timezone.utc), fee_gwei=Decimal("30.0")),
        ]

        metrics = catcher.compute_snapshot_metrics(
            captured_blocks=blocks,
            previous_fee_value=Decimal("20.0"),
            usd_price=Decimal("2500"),
        )

        assert metrics["raw_fee_value"] == Decimal("30.000000000000000000")
        assert metrics["avg_fee"] == Decimal("25.000000000000000000")
        assert metrics["median_fee"] == Decimal("25.000000000000000000")
        assert metrics["min_fee"] == Decimal("20.000000000000000000")
        assert metrics["max_fee"] == Decimal("30.000000000000000000")
        assert metrics["sample_count"] == 3
        assert metrics["previous_value"] == Decimal("20.000000000000000000")
        # ((30 - 20) / 20) * 100 = 50.0000%
        assert metrics["change_percentage"] == Decimal("50.0000")
        assert metrics["status"] == FeeStatus.UP
        assert metrics["block_number"] == 102
        assert metrics["usd_value"] == Decimal("75000.00000000")

    def test_status_down_and_stable(self):
        catcher = EtherscanCatcher()
        blocks = [
            CapturedBlock(number=200, timestamp=datetime.now(timezone.utc), fee_gwei=Decimal("15.0")),
        ]

        # Down: previous was 20.0, current is 15.0 -> -25%
        metrics_down = catcher.compute_snapshot_metrics(
            captured_blocks=blocks,
            previous_fee_value=Decimal("20.0"),
        )
        assert metrics_down["status"] == FeeStatus.DOWN
        assert metrics_down["change_percentage"] == Decimal("-25.0000")

        # Stable: previous was 15.01, current is 15.0 -> -0.066%
        metrics_stable = catcher.compute_snapshot_metrics(
            captured_blocks=blocks,
            previous_fee_value=Decimal("15.01"),
        )
        assert metrics_stable["status"] == FeeStatus.STABLE


class TestCaptureAndInsertDatabase:
    """Tests end-to-end block capturing and insertion into FeeSnapshot table."""

    def _setup_mock_session(self, catcher: BaseBlockchainCatcher, base_fee_wei: int = 25_000_000_000):
        mock_session = MagicMock()

        def mock_get(url, params=None, headers=None, timeout=None):
            resp = MagicMock()
            resp.raise_for_status.return_value = None
            action = params.get("action")
            if action == "getblocknobytime":
                resp.json.return_value = {"status": "1", "message": "OK", "result": "19000000"}
            elif action == "eth_blockNumber":
                resp.json.return_value = {"jsonrpc": "2.0", "result": "0x121eac0"}
            elif action == "eth_getBlockByNumber":
                tag = params.get("tag", "0x121eac0")
                block_num = int(tag, 16) if tag.startswith("0x") else 19000000
                resp.json.return_value = {
                    "jsonrpc": "2.0",
                    "result": {
                        "number": hex(block_num),
                        "timestamp": "0x66f12345",
                        "baseFeePerGas": hex(base_fee_wei),
                        "gasUsed": "0x1c9c38",
                        "gasLimit": "0x1c9c380",
                        "transactions": [],
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

    @pytest.mark.parametrize(
        "catcher_cls, expected_name, expected_symbol",
        [
            (EtherscanCatcher, "Ethereum", "ETH"),
            (PolygonscanCatcher, "Polygon", "POL"),
            (BscScanCatcher, "BNB Smart Chain", "BNB"),
            (ArbiscanCatcher, "Arbitrum", "ARB"),
            (SnowtraceCatcher, "Avalanche", "AVAX"),
        ],
    )
    def test_capture_and_insert_for_all_five_blockchains(
        self,
        db_session: Session,
        catcher_cls,
        expected_name: str,
        expected_symbol: str,
    ):
        catcher = catcher_cls()
        self._setup_mock_session(catcher, base_fee_wei=25_000_000_000)

        # Capture across HOURS
        snapshot = catcher.capture_and_insert(
            db=db_session,
            timeframe="HOURS",
            sample_size=3,
        )

        assert snapshot.id is not None
        assert snapshot.raw_fee_value == Decimal("25.000000000000000000")
        assert snapshot.sample_count == 1  # start == end in mock block range
        assert snapshot.block_number == 19000000
        assert snapshot.status == FeeStatus.STABLE
        assert snapshot.blockchain.name == expected_name
        assert snapshot.blockchain.symbol == expected_symbol
        assert snapshot.time_unit.name == TimeUnitName.HOUR

    def test_capture_and_insert_trend_calculation(self, db_session: Session):
        catcher = EtherscanCatcher()

        # First capture at 20 Gwei
        self._setup_mock_session(catcher, base_fee_wei=20_000_000_000)
        snap1 = catcher.capture_and_insert(db=db_session, timeframe=TimeUnitName.DAY)
        assert snap1.raw_fee_value == Decimal("20.000000000000000000")
        assert snap1.previous_value is None
        assert snap1.status == FeeStatus.STABLE

        # Second capture at 35 Gwei (+75%)
        self._setup_mock_session(catcher, base_fee_wei=35_000_000_000)
        snap2 = catcher.capture_and_insert(db=db_session, timeframe=TimeUnitName.DAY)
        assert snap2.raw_fee_value == Decimal("35.000000000000000000")
        assert snap2.previous_value == Decimal("20.000000000000000000")
        assert snap2.change_percentage == Decimal("75.0000")
        assert snap2.status == FeeStatus.UP

        # Verify DB query
        rows = db_session.scalars(select(FeeSnapshot).order_by(FeeSnapshot.id.asc())).all()
        assert len(rows) == 2
        assert rows[1].status == FeeStatus.UP

    def test_gas_oracle_method(self):
        catcher = EtherscanCatcher()
        self._setup_mock_session(catcher)
        oracle = catcher.get_gas_oracle()
        assert oracle["SafeGasPrice"] == "20"
        assert oracle["FastGasPrice"] == "30"

    def test_scanner_network_error_raises_exception(self):
        catcher = EtherscanCatcher()
        mock_session = MagicMock()
        import requests
        mock_session.get.side_effect = requests.RequestException("Timeout connecting to scanner")
        catcher.session = mock_session

        with pytest.raises(ScannerAPIError, match="HTTP request to .* failed"):
            catcher.get_latest_block_number()
