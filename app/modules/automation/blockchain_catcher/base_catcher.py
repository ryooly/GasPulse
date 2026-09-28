from __future__ import annotations

import enum
import logging
import os
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Sequence

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.blockchains import Blockchain
from app.models.fee_snapshot_models import FeeSnapshot, FeeStatus
from app.models.time_unit_models import TimeUnit, TimeUnitName
from db.base import utcnow

logger = logging.getLogger(__name__)


# errorHandler
class BlockchainCatcherError(Exception):
    """Base exception for all blockchain catcher errors."""


class ScannerAPIError(BlockchainCatcherError):
    """Raised when scanner API returns an error or unexpected response."""


class InvalidTimeframeError(BlockchainCatcherError):
    """Raised when an unsupported timeframe identifier is supplied."""


@dataclass
class CapturedBlock:

    number: int
    timestamp: datetime
    fee_gwei: Decimal
    base_fee_per_gas_wei: int | None = None
    gas_used: int | None = None
    gas_limit: int | None = None
    raw_data: dict[str, Any] | None = None


def _quantize_decimal(value: Decimal | None, places: str = "0.000000000000000001") -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal(places))


class BaseBlockchainCatcher:

    BLOCKCHAIN_NAME: str = "Unknown"
    BLOCKCHAIN_SYMBOL: str = "UNK"
    CHAIN_ID: int | None = None
    NATIVE_CURRENCY: str = "ETH"
    DEFAULT_API_URL: str = "https://api.example.com/api"
    DEFAULT_API_KEY: str = "YOUR_API_KEY"
    DEFAULT_USD_PRICE: Decimal | None = None

    TIMEFRAME_MAP: dict[str, tuple[TimeUnitName, int]] = {
        "hour": (TimeUnitName.HOUR, 3600),
        "hours": (TimeUnitName.HOUR, 3600),
        "day": (TimeUnitName.DAY, 86400),
        "days": (TimeUnitName.DAY, 86400),
        "week": (TimeUnitName.WEEK, 604800),
        "weeks": (TimeUnitName.WEEK, 604800),
    }

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 15.0,
        blockchain_name: str | None = None,
        blockchain_symbol: str | None = None,
        chain_id: int | None = None,
        native_currency: str | None = None,
        default_usd_price: Decimal | None = None,
    ) -> None:
        self.api_url = (api_url or self.DEFAULT_API_URL).rstrip("/")
        self.api_key = api_key or self.DEFAULT_API_KEY
        self.session = session or requests.Session()
        self.timeout = timeout
        self.blockchain_name = blockchain_name or self.BLOCKCHAIN_NAME
        self.blockchain_symbol = blockchain_symbol or self.BLOCKCHAIN_SYMBOL
        self.chain_id = chain_id if chain_id is not None else self.CHAIN_ID
        self.native_currency = native_currency or self.NATIVE_CURRENCY
        self.default_usd_price = default_usd_price or self.DEFAULT_USD_PRICE


    def resolve_timeframe(self, timeframe: TimeUnitName | str) -> tuple[TimeUnitName, int]:
        if isinstance(timeframe, TimeUnitName):
            seconds = {
                TimeUnitName.HOUR: 3600,
                TimeUnitName.DAY: 86400,
                TimeUnitName.WEEK: 604800,
            }.get(timeframe, 3600)
            return timeframe, seconds

        normalized = str(timeframe).strip().lower()
        if normalized in self.TIMEFRAME_MAP:
            return self.TIMEFRAME_MAP[normalized]

        valid = ", ".join(self.TIMEFRAME_MAP.keys())
        raise InvalidTimeframeError(
            f"Unsupported timeframe '{timeframe}'. Must be one of: {valid} or TimeUnitName enum."
        )


    def make_scanner_request(self, params: dict[str, Any]) -> dict[str, Any]:
        query_params = dict(params)
        if "apikey" not in query_params and self.api_key:
            query_params["apikey"] = self.api_key

        headers = {"User-Agent": f"GasPulse-{self.blockchain_name}/1.0"}

        try:
            response = self.session.get(
                self.api_url,
                params=query_params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            logger.error("Network error requesting %s: %s", self.api_url, exc)
            raise ScannerAPIError(f"HTTP request to {self.api_url} failed: {exc}") from exc
        except ValueError as exc:
            logger.error("Invalid JSON from %s: %s", self.api_url, exc)
            raise ScannerAPIError(f"Malformed JSON response from {self.api_url}: {exc}") from exc

        return data


    def get_latest_block_number(self) -> int:
        params = {
            "module": "proxy",
            "action": "eth_blockNumber",
        }
        data = self.make_scanner_request(params)

        if "result" in data and isinstance(data["result"], str):
            try:
                return int(data["result"], 16)
            except ValueError as exc:
                raise ScannerAPIError(f"Cannot parse block number hex '{data['result']}': {exc}") from exc

        raise ScannerAPIError(f"Unexpected eth_blockNumber response format: {data}")

    def get_block_number_by_timestamp(
        self,
        timestamp: int,
        closest: str = "before",
    ) -> int:
        params = {
            "module": "block",
            "action": "getblocknobytime",
            "timestamp": int(timestamp),
            "closest": closest,
        }
        data = self.make_scanner_request(params)

        if data.get("status") == "1" and "result" in data:
            try:
                return int(data["result"])
            except (ValueError, TypeError) as exc:
                raise ScannerAPIError(f"Cannot parse block number from '{data.get('result')}': {exc}") from exc

        message = data.get("message", "Unknown scanner error")
        result = data.get("result", "")
        raise ScannerAPIError(
            f"Scanner error fetching block for timestamp {timestamp}: {message} ({result})"
        )

    def get_block_by_number(self, block_number: int, full_transactions: bool = False) -> dict[str, Any]:
        hex_tag = hex(block_number)
        params = {
            "module": "proxy",
            "action": "eth_getBlockByNumber",
            "tag": hex_tag,
            "boolean": "true" if full_transactions else "false",
        }
        data = self.make_scanner_request(params)

        if "result" in data and isinstance(data["result"], dict):
            return data["result"]

        raise ScannerAPIError(f"Failed to fetch block {block_number} ({hex_tag}): {data}")

    def extract_block_fee(self, block_data: dict[str, Any]) -> Decimal:
        base_fee_hex = block_data.get("baseFeePerGas")
        if base_fee_hex and isinstance(base_fee_hex, str):
            try:
                base_fee_wei = int(base_fee_hex, 16)
                if base_fee_wei > 0:
                    return Decimal(base_fee_wei) / Decimal(10**9)
            except ValueError:
                pass

        transactions = block_data.get("transactions")
        if transactions and isinstance(transactions, list):
            tx_prices: list[int] = []
            for tx in transactions:
                if isinstance(tx, dict) and "gasPrice" in tx and tx["gasPrice"]:
                    try:
                        tx_prices.append(int(tx["gasPrice"], 16))
                    except (ValueError, TypeError):
                        continue
            if tx_prices:
                avg_tx_wei = sum(tx_prices) // len(tx_prices)
                return Decimal(avg_tx_wei) / Decimal(10**9)

       
        try:
            gas_price_data = self.make_scanner_request({"module": "proxy", "action": "eth_gasPrice"})
            if "result" in gas_price_data and isinstance(gas_price_data["result"], str):
                wei_val = int(gas_price_data["result"], 16)
                return Decimal(wei_val) / Decimal(10**9)
        except Exception as exc:
            logger.warning("Could not fallback to eth_gasPrice: %s", exc)

        return Decimal("1.0")


    def fetch_blocks_for_timeframe(
        self,
        timeframe: TimeUnitName | str,
        sample_size: int = 10,
        end_datetime: datetime | None = None,
    ) -> list[CapturedBlock]:
        _unit_name, interval_seconds = self.resolve_timeframe(timeframe)
        end_time = end_datetime or datetime.now(timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        start_time = end_time - timedelta(seconds=interval_seconds)

        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())

        try:
            start_block_num = self.get_block_number_by_timestamp(start_ts, closest="after")
        except Exception:
            start_block_num = self.get_block_number_by_timestamp(start_ts, closest="before")

        try:
            end_block_num = self.get_block_number_by_timestamp(end_ts, closest="before")
        except Exception:
            end_block_num = self.get_latest_block_number()

        if start_block_num > end_block_num:
            start_block_num = end_block_num

        total_blocks = end_block_num - start_block_num + 1
        count = max(1, min(sample_size, total_blocks))

        if count == 1:
            block_numbers = [end_block_num]
        else:
            step = (end_block_num - start_block_num) / (count - 1)
            block_numbers = sorted(
                list({round(start_block_num + i * step) for i in range(count)})
            )
            if block_numbers[-1] != end_block_num:
                block_numbers[-1] = end_block_num

        captured: list[CapturedBlock] = []
        for b_num in block_numbers:
            try:
                b_data = self.get_block_by_number(b_num)
                fee = self.extract_block_fee(b_data)

                ts_hex = b_data.get("timestamp")
                if ts_hex and isinstance(ts_hex, str):
                    ts_val = datetime.fromtimestamp(int(ts_hex, 16), tz=timezone.utc)
                else:
                    ts_val = end_time

                base_fee_hex = b_data.get("baseFeePerGas")
                base_fee_wei = int(base_fee_hex, 16) if base_fee_hex else None

                gas_used_hex = b_data.get("gasUsed")
                gas_used = int(gas_used_hex, 16) if gas_used_hex else None

                gas_limit_hex = b_data.get("gasLimit")
                gas_limit = int(gas_limit_hex, 16) if gas_limit_hex else None

                captured.append(
                    CapturedBlock(
                        number=b_num,
                        timestamp=ts_val,
                        fee_gwei=fee,
                        base_fee_per_gas_wei=base_fee_wei,
                        gas_used=gas_used,
                        gas_limit=gas_limit,
                        raw_data=b_data,
                    )
                )
            except Exception as exc:
                logger.warning("Failed capturing block %s for %s: %s", b_num, self.blockchain_name, exc)

        if not captured:
            raise ScannerAPIError(
                f"Failed to capture any blocks for {self.blockchain_name} in timeframe {timeframe}"
            )

        return captured


    def compute_snapshot_metrics(
        self,
        captured_blocks: Sequence[CapturedBlock],
        previous_fee_value: Decimal | None = None,
        usd_price: Decimal | None = None,
    ) -> dict[str, Any]:
        if not captured_blocks:
            raise ValueError("captured_blocks cannot be empty")

        fees = [b.fee_gwei for b in captured_blocks]
        latest_block = captured_blocks[-1]
        raw_fee = latest_block.fee_gwei

        avg_fee = sum(fees) / Decimal(len(fees))
        median_fee = Decimal(str(statistics.median([float(f) for f in fees])))
        min_fee = min(fees)
        max_fee = max(fees)
        sample_count = len(fees)

        change_pct: Decimal | None = None
        if previous_fee_value is not None and previous_fee_value > Decimal("0"):
            change_pct = ((raw_fee - previous_fee_value) / previous_fee_value) * Decimal("100")
            change_pct = _quantize_decimal(change_pct, "0.0001")

        if change_pct is None:
            status = FeeStatus.STABLE
        elif change_pct > Decimal("0.5"):
            status = FeeStatus.UP
        elif change_pct < Decimal("-0.5"):
            status = FeeStatus.DOWN
        else:
            status = FeeStatus.STABLE

        price = usd_price or self.default_usd_price
        usd_val = _quantize_decimal(raw_fee * price, "0.00000001") if price else None

        return {
            "raw_fee_value": _quantize_decimal(raw_fee),
            "usd_value": usd_val,
            "avg_fee": _quantize_decimal(avg_fee),
            "median_fee": _quantize_decimal(median_fee),
            "min_fee": _quantize_decimal(min_fee),
            "max_fee": _quantize_decimal(max_fee),
            "sample_count": sample_count,
            "previous_value": _quantize_decimal(previous_fee_value),
            "status": status,
            "change_percentage": change_pct,
            "block_number": latest_block.number,
        }


# repository is nedeed
    def ensure_blockchain_record(self, db: Session) -> Blockchain:
        stmt = select(Blockchain).where(
            func.lower(Blockchain.name) == self.blockchain_name.strip().lower()
        )
        chain = db.scalars(stmt).first()
        if chain is None:
            chain = Blockchain(
                name=self.blockchain_name,
                symbol=self.blockchain_symbol,
                chain_id=self.chain_id,
                native_currency=self.native_currency,
                explorer_api_url=self.api_url,
                is_active=True,
            )
            db.add(chain)
            db.flush()
        return chain

    def ensure_time_unit_record(
        self,
        db: Session,
        time_unit_name: TimeUnitName,
        interval_seconds: int,
    ) -> TimeUnit:
        stmt = select(TimeUnit).where(TimeUnit.name == time_unit_name)
        unit = db.scalars(stmt).first()
        if unit is None:
            unit = TimeUnit(
                name=time_unit_name,
                interval_seconds=interval_seconds,
            )
            db.add(unit)
            db.flush()
        return unit

    def get_latest_snapshot(
        self,
        db: Session,
        blockchain_id: int,
        time_unit_id: int,
    ) -> FeeSnapshot | None:
        stmt = (
            select(FeeSnapshot)
            .where(FeeSnapshot.blockchain_id == blockchain_id)
            .where(FeeSnapshot.time_unit_id == time_unit_id)
            .order_by(FeeSnapshot.recorded_at.desc())
            .limit(1)
        )
        return db.scalars(stmt).first()

    def capture_and_insert(
        self,
        db: Session,
        timeframe: TimeUnitName | str,
        sample_size: int = 10,
        usd_price: Decimal | None = None,
        autocommit: bool = True,
    ) -> FeeSnapshot:
        unit_name, interval_seconds = self.resolve_timeframe(timeframe)
        blockchain = self.ensure_blockchain_record(db)
        time_unit = self.ensure_time_unit_record(db, unit_name, interval_seconds)
        prev_snapshot = self.get_latest_snapshot(db, blockchain.id, time_unit.id)
        prev_value = prev_snapshot.raw_fee_value if prev_snapshot else None

        captured_blocks = self.fetch_blocks_for_timeframe(
            timeframe=unit_name,
            sample_size=sample_size,
        )

        metrics = self.compute_snapshot_metrics(
            captured_blocks=captured_blocks,
            previous_fee_value=prev_value,
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
            recorded_at=utcnow(),
            created_at=utcnow(),
        )

        db.add(snapshot)
        if autocommit:
            db.commit()
            db.refresh(snapshot)
        else:
            db.flush()

        logger.info(
            "Captured and inserted FeeSnapshot for %s [%s]: fee=%s %s status=%s",
            self.blockchain_name,
            unit_name.value,
            snapshot.raw_fee_value,
            self.blockchain_symbol,
            snapshot.status.value,
        )
        return snapshot


__all__ = [
    "BaseBlockchainCatcher",
    "BlockchainCatcherError",
    "CapturedBlock",
    "InvalidTimeframeError",
    "ScannerAPIError",
]
