from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select

from app.models.blockchains import Blockchain
from app.models.fee_snapshot_models import FeeSnapshot, FeeStatus
from app.models.time_unit_models import TimeUnit, TimeUnitName
from app.modules.automation.blockchain_catcher.base_client import (
    BaseScannerClient,
    ScannerConfig,
)
from app.modules.automation.blockchain_catcher.exceptions import (
    InvalidTimeframeError,
    ScannerAPIError,
)

WEI_PER_GWEI = Decimal(10) ** 9

_TIMEFRAME_MAP: dict[str, tuple[TimeUnitName, int]] = {
    "hour": (TimeUnitName.HOUR, 3600),
    "day": (TimeUnitName.DAY, 86400),
    "week": (TimeUnitName.WEEK, 604800),
}

STABLE_THRESHOLD = Decimal("1")

_Q18 = Decimal("0.000000000000000001")
_Q4 = Decimal("0.0001")
_Q8 = Decimal("0.00000001")


def _quantize(value: Decimal, exp: Decimal) -> Decimal:
    return value.quantize(exp, rounding=ROUND_HALF_UP)


@dataclass
class CapturedBlock:

    number: int
    timestamp: datetime
    fee_gwei: Decimal
    gas_used: int | None = None
    gas_limit: int | None = None


class BaseBlockchainCatcher(BaseScannerClient):

    blockchain_name: str = "Base"
    blockchain_symbol: str = "BASE"

    def __init__(
        self,
        config: ScannerConfig | None = None,
        api_url: str | None = None,
        api_key: str | None = None,
        session=None,
        **config_kwargs,
    ):
        if config is None:
            config = ScannerConfig(
                api_url=api_url or "https://api.etherscan.io/api",
                api_key=api_key or "",
                **config_kwargs,
            )
        elif api_url is not None:
            config.api_url = api_url
            if api_key is not None:
                config.api_key = api_key
        super().__init__(config, session=session)

# tambahakan algorithm ketika config gak ada api key sebiknya gimana dan tambahkan algorithm nanti dengan mebandingkan dengan namaya tanpa perlu api url dri params alias hapus aja 


    def resolve_timeframe(self, timeframe) -> tuple[TimeUnitName, int]:
        if isinstance(timeframe, TimeUnitName):
            key = timeframe.value
        else:
            key = str(timeframe).strip().lower().rstrip("s")
        resolved = _TIMEFRAME_MAP.get(key)
        if resolved is None:
            raise InvalidTimeframeError(f"Unknown timeframe: {timeframe!r}")
        return resolved

    def get_latest_block_number(self) -> int:
        data = self.request({"module": "proxy", "action": "eth_blockNumber"})
        return int(data["result"], 16) # ini adlaah blok permintaan nanti di design sendiri sehingga bisa di pake non eth

    def get_block_number_by_timestamp(self, timestamp: datetime, closest: str = "before") -> int:
        ts = int(timestamp.timestamp())
        data = self.request({
            "module": "block",
            "action": "getblocknobytime",
            "timestamp": ts,
            "closest": closest,
        })
        if str(data.get("status")) != "1" or not data.get("result"):
            raise ScannerAPIError(f"getblocknobytime failed for timestamp {ts}: {data}")
        return int(data["result"])

    def get_block_by_number(self, number: int) -> CapturedBlock:
        data = self.request({
            "module": "proxy",
            "action": "eth_getBlockByNumber",
            "tag": hex(number),
            "boolean": "false",
        })
        result = data.get("result") or {}
        base_fee_wei = int(result.get("baseFeePerGas", "0x0"), 16)
        return CapturedBlock(
            number=int(result.get("number", hex(number)), 16),
            timestamp=datetime.fromtimestamp(int(result["timestamp"], 16), tz=timezone.utc),
            fee_gwei=Decimal(base_fee_wei) / WEI_PER_GWEI,
            gas_used=int(result["gasUsed"], 16) if result.get("gasUsed") else None,
            gas_limit=int(result["gasLimit"], 16) if result.get("gasLimit") else None,
        )

    def get_gas_oracle(self) -> dict:
        data = self.request({"module": "gastracker", "action": "gasoracle"})
        return data.get("result", {})

    def fetch_blocks_by_time_range(
        self, seconds: int, sample_size: int = 5,
    ) -> list[CapturedBlock]:
        now = datetime.now(timezone.utc)
        start_block = self.get_block_number_by_timestamp(now - timedelta(seconds=seconds))
        end_block = self.get_latest_block_number()
        return self._sample_blocks(start_block, end_block, sample_size)

    def _sample_blocks(self, start_block: int, end_block: int, sample_size: int) -> list[CapturedBlock]:
        if end_block <= start_block:
            numbers = [end_block]
        else:
            span = end_block - start_block
            count = max(1, min(sample_size, span + 1))
            step = span / (count - 1) if count > 1 else 0
            numbers = [int(round(start_block + i * step)) for i in range(count)]
            if numbers[-1] != end_block:
                numbers.append(end_block)
        return [self.get_block_by_number(n) for n in dict.fromkeys(numbers)]


    def compute_snapshot_metrics(
        self,
        captured_blocks: list[CapturedBlock],
        previous_fee_value: Decimal | None = None,
        usd_price: Decimal | None = None,
    ) -> dict:
        if not captured_blocks:
            raise ValueError("captured_blocks must not be empty")

        ordered = sorted(captured_blocks, key=lambda b: b.number)
        latest = ordered[-1]
        fees = [b.fee_gwei for b in ordered]

        raw_fee_value = _quantize(latest.fee_gwei, _Q18)
        avg_fee = _quantize(sum(fees) / Decimal(len(fees)), _Q18)
        median_fee = _quantize(self._median(fees), _Q18)
        min_fee = _quantize(min(fees), _Q18)
        max_fee = _quantize(max(fees), _Q18)

        previous_value = _quantize(previous_fee_value, _Q18) if previous_fee_value is not None else None

        change_percentage: Decimal | None = None
        status = FeeStatus.STABLE
        if previous_value is not None and previous_value != 0:
            change = (raw_fee_value - previous_value) / previous_value * Decimal(100)
            change_percentage = _quantize(change, _Q4)
            if change_percentage > STABLE_THRESHOLD:
                status = FeeStatus.UP
            elif change_percentage < -STABLE_THRESHOLD:
                status = FeeStatus.DOWN

        usd_value = (
            _quantize(raw_fee_value * usd_price, _Q8) if usd_price is not None else None
        )

        return {
            "raw_fee_value": raw_fee_value,
            "usd_value": usd_value,
            "avg_fee": avg_fee,
            "median_fee": median_fee,
            "min_fee": min_fee,
            "max_fee": max_fee,
            "sample_count": len(ordered),
            "previous_value": previous_value,
            "status": status,
            "change_percentage": change_percentage,
            "block_number": latest.number,
        }

    @staticmethod
    def _median(fees: list[Decimal]) -> Decimal:
        ordered = sorted(fees)
        n = len(ordered)
        mid = n // 2
        if n % 2 == 1:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / Decimal(2)

    def capture_and_insert(
        self,
        db,
        timeframe,
        sample_size: int = 5,
        usd_price: Decimal | None = None,
    ) -> FeeSnapshot:
        unit, seconds = self.resolve_timeframe(timeframe)
        blocks = self.fetch_blocks_by_time_range(seconds=seconds, sample_size=sample_size)

        blockchain = self._get_or_create_blockchain(db)
        time_unit = self._get_or_create_time_unit(db, unit, seconds)

        previous_fee = self._get_previous_fee(db, blockchain.id, time_unit.id)
        metrics = self.compute_snapshot_metrics(
            captured_blocks=blocks,
            previous_fee_value=previous_fee,
            usd_price=usd_price,
        )

        snapshot = FeeSnapshot(
            blockchain_id=blockchain.id,
            time_unit_id=time_unit.id,
            raw_fee_value=metrics["raw_fee_value"],
            usd_value=metrics["usd_value"],
            avg_fee=metrics["avg_fee"],
            median_fee=metrics["median_fee"],
            min_fee=metrics["min_fee"],
            max_fee=metrics["max_fee"],
            sample_count=metrics["sample_count"],
            previous_value=metrics["previous_value"],
            status=metrics["status"],
            change_percentage=metrics["change_percentage"],
            block_number=metrics["block_number"],
            recorded_at=datetime.now(timezone.utc),
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        return snapshot

    def _get_or_create_blockchain(self, db) -> Blockchain:
        blockchain = db.scalars(
            select(Blockchain).where(Blockchain.name == self.blockchain_name)
        ).first()
        if blockchain is None:
            blockchain = Blockchain(
                name=self.blockchain_name,
                symbol=self.blockchain_symbol,
                native_currency=self.blockchain_symbol,
                explorer_api_url=self.config.api_url,
                is_active=True,
            )
            db.add(blockchain)
            db.commit()
            db.refresh(blockchain)
        return blockchain

    @staticmethod
    def _get_or_create_time_unit(db, unit: TimeUnitName, seconds: int) -> TimeUnit:
        time_unit = db.scalars(
            select(TimeUnit).where(TimeUnit.name == unit)
        ).first()
        if time_unit is None:
            time_unit = TimeUnit(name=unit, interval_seconds=seconds)
            db.add(time_unit)
            db.commit()
            db.refresh(time_unit)
        return time_unit

    @staticmethod
    def _get_previous_fee(db, blockchain_id: int, time_unit_id: int) -> Decimal | None:
        prior = db.scalars(
            select(FeeSnapshot)
            .where(
                FeeSnapshot.blockchain_id == blockchain_id,
                FeeSnapshot.time_unit_id == time_unit_id,
            )
            .order_by(FeeSnapshot.id.desc())
            .limit(1)
        ).first()
        return prior.raw_fee_value if prior is not None else None


__all__ = ["CapturedBlock", "BaseBlockchainCatcher"]
