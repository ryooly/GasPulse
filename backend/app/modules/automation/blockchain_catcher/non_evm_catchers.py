from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

import requests

from app.exception import InvalidTimeframeError, ScannerAPIError
from app.models.fee_snapshot_models import FeeSnapshot, FeeStatus
from app.models.time_unit_models import TimeUnitName
from app.modules.automation.blockchain_catcher.base_catcher import BaseBlockchainCatcher, CapturedBlock
from app.modules.automation.blockchain_catcher.base_client import BaseScannerClient, ScannerConfig
from app.modules.automation.repository.catcher_repository import CatcherRepository

_Q18 = Decimal("0.000000000000000001")
_Q4 = Decimal("0.0001")
_Q8 = Decimal("0.00000001")
STABLE_THRESHOLD = Decimal("1")


def _quantize(value: Decimal, exp: Decimal) -> Decimal:
    return value.quantize(exp, rounding=ROUND_HALF_UP)


_TIMEFRAME_MAP = {
    "hour": (TimeUnitName.HOUR, 3600),
    "day": (TimeUnitName.DAY, 86400),
    "week": (TimeUnitName.WEEK, 604800),
}


class BaseExternalCatcher(BaseScannerClient):
    blockchain_name: str = "BaseExternal"
    blockchain_symbol: str = "EXT"
    env_prefix: str = ""
    default_api_url: str = ""
    default_api_key: str = ""

    def __init__(self, config: ScannerConfig | None = None, session=None, **config_kwargs):
        if config is None:
            config = ScannerConfig.from_env(
                env_prefix=self.env_prefix,
                default_api_url=self.default_api_url,
                default_api_key=self.default_api_key,
            )
        super().__init__(config, session=session)

    def resolve_timeframe(self, timeframe):
        if isinstance(timeframe, TimeUnitName):
            key = timeframe.value
        else:
            key = str(timeframe).strip().lower().rstrip("s")
        resolved = _TIMEFRAME_MAP.get(key)
        if resolved is None:
            raise InvalidTimeframeError(f"Unknown timeframe: {timeframe!r}")
        return resolved

    def fetch_fee_samples(self, seconds: int, sample_size: int = 5) -> list[CapturedBlock]:
        raise NotImplementedError

    def compute_snapshot_metrics(self, captured_blocks, previous_fee_value=None, usd_price=None):
        if not captured_blocks:
            raise ValueError("captured_blocks must not be empty")
        ordered = sorted(captured_blocks, key=lambda b: b.number)
        latest = ordered[-1]
        fees = [b.fee_gwei for b in ordered]
        raw_fee_value = _quantize(latest.fee_gwei, _Q18)
        avg_fee = _quantize(sum(fees) / Decimal(len(fees)), _Q18)
        median_fee = _quantize(BaseBlockchainCatcher._median(fees), _Q18)
        min_fee = _quantize(min(fees), _Q18)
        max_fee = _quantize(max(fees), _Q18)
        previous_value = _quantize(previous_fee_value, _Q18) if previous_fee_value is not None else None
        change_percentage = None
        status = FeeStatus.STABLE
        if previous_value is not None and previous_value != 0:
            change = (raw_fee_value - previous_value) / previous_value * Decimal(100)
            change_percentage = _quantize(change, _Q4)
            if change_percentage > STABLE_THRESHOLD:
                status = FeeStatus.UP
            elif change_percentage < -STABLE_THRESHOLD:
                status = FeeStatus.DOWN
        usd_value = _quantize(raw_fee_value * usd_price, _Q8) if usd_price is not None else None
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

    def capture_and_insert(self, db, timeframe, sample_size: int = 5, usd_price: Decimal | None = None) -> FeeSnapshot:
        repo = CatcherRepository(db)
        unit, seconds = self.resolve_timeframe(timeframe)
        blocks = self.fetch_fee_samples(seconds=seconds, sample_size=sample_size)
        blockchain = repo.get_or_create_blockchain(self.blockchain_name, self.blockchain_symbol, self.config.api_url)
        time_unit = repo.get_or_create_time_unit(unit, seconds)
        previous_fee = repo.get_previous_fee(blockchain.id, time_unit.id)
        metrics = self.compute_snapshot_metrics(blocks, previous_fee_value=previous_fee, usd_price=usd_price)
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
        return repo.insert_snapshot(snapshot)


class BitcoinMempoolCatcher(BaseExternalCatcher):
    """Samples Bitcoin fee rates (sat/vB) from mempool.space public API."""

    blockchain_name = "Bitcoin"
    blockchain_symbol = "BTC"
    env_prefix = "BITCOIN_MEMPOOL"
    default_api_url = "https://mempool.space/api"
    default_api_key = ""

    def _get_json(self, path: str):
        base = self.config.api_url.rstrip("/")
        try:
            resp = self.session.get(f"{base}{path}", timeout=self.config.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            raise ScannerAPIError(f"Bitcoin API request failed for {path}: {exc}") from exc
        except ValueError as exc:
            raise ScannerAPIError(f"Bitcoin API returned invalid JSON for {path}: {exc}") from exc

    def fetch_fee_samples(self, seconds: int, sample_size: int = 5) -> list[CapturedBlock]:
        rec = self._get_json("/v1/fees/recommended") or {}
        tip = self._get_json("/blocks/tip/height")
        blocks = self._get_json("/v1/blocks") or []
        if not isinstance(blocks, list):
            blocks = []

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=max(1, int(seconds)))
        samples: list[CapturedBlock] = []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            try:
                ts = datetime.fromtimestamp(int(b.get("timestamp", 0)), tz=timezone.utc)
            except Exception:
                ts = now
            if ts < cutoff and len(samples) >= 1:
                continue
            median_fee = (b.get("extras") or {}).get("medianFee")
            if median_fee is None:
                median_fee = rec.get("halfHourFee") or rec.get("fastestFee") or 0
            try:
                fee_val = Decimal(str(median_fee))
            except Exception:
                fee_val = Decimal("0")
            try:
                height = int(b.get("height", 0))
            except Exception:
                height = 0
            samples.append(CapturedBlock(number=height, timestamp=ts, fee_gwei=fee_val))

        if not samples:
            fee = rec.get("halfHourFee") or rec.get("fastestFee") or rec.get("hourFee") or 0
            try:
                fee_val = Decimal(str(fee))
            except Exception:
                fee_val = Decimal("0")
            try:
                height = int(tip)
            except Exception:
                height = 0
            samples = [CapturedBlock(number=height, timestamp=now, fee_gwei=fee_val)]
        return samples[: max(1, int(sample_size))]


class SolanaCatcher(BaseExternalCatcher):
    """Samples Solana transaction fee estimates (lamports) via JSON-RPC."""

    blockchain_name = "Solana"
    blockchain_symbol = "SOL"
    env_prefix = "SOLANA_RPC"
    default_api_url = "https://api.mainnet-beta.solana.com"
    default_api_key = ""

    def _rpc(self, method: str, params=None):
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        try:
            resp = self.session.post(self.config.api_url, json=payload, headers=headers, timeout=self.config.timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise ScannerAPIError(f"Solana RPC request failed for {method}: {exc}") from exc
        except ValueError as exc:
            raise ScannerAPIError(f"Solana RPC returned invalid JSON for {method}: {exc}") from exc
        if isinstance(data, dict):
            if data.get("error"):
                raise ScannerAPIError(f"Solana RPC error for {method}: {data['error']}")
            return data.get("result")
        return data

    def fetch_fee_samples(self, seconds: int, sample_size: int = 5) -> list[CapturedBlock]:
        slot = self._rpc("getSlot") or 0
        fees = self._rpc("getRecentPrioritizationFees", []) or []
        if not isinstance(fees, list):
            fees = []
        now = datetime.now(timezone.utc)
        samples: list[CapturedBlock] = []
        for item in list(fees)[-max(1, int(sample_size)):]:
            if not isinstance(item, dict):
                continue
            prio = item.get("prioritizationFee", 0)
            try:
                fee_val = Decimal("5000") + Decimal(str(prio))
            except Exception:
                fee_val = Decimal("5000")
            try:
                item_slot = int(item.get("slot", slot) or 0)
            except Exception:
                item_slot = int(slot) if str(slot).isdigit() else 0
            samples.append(CapturedBlock(number=item_slot, timestamp=now, fee_gwei=fee_val))
        if not samples:
            try:
                slot_num = int(slot)
            except Exception:
                slot_num = 0
            samples = [CapturedBlock(number=slot_num, timestamp=now, fee_gwei=Decimal("5000"))]
        return samples


class PolkadotCatcher(BaseExternalCatcher):
    """Samples Polkadot block fees via Subscan API when an API key is available."""

    blockchain_name = "Polkadot"
    blockchain_symbol = "DOT"
    env_prefix = "POLKADOT_SUBSCAN"
    default_api_url = "https://polkadot.api.subscan.io"
    default_api_key = ""

    def fetch_fee_samples(self, seconds: int, sample_size: int = 5) -> list[CapturedBlock]:
        base = self.config.api_url.rstrip("/")
        if not self.config.api_key:
            raise ScannerAPIError(
                "Polkadot Subscan API key is required (set POLKADOT_SUBSCAN_API_KEY)."
            )
        headers = {"Content-Type": "application/json", "X-API-Key": self.config.api_key}
        try:
            resp = self.session.post(
                f"{base}/api/scan/blocks",
                json={"row": max(1, int(sample_size)), "page": 0},
                headers=headers,
                timeout=self.config.timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as exc:
            raise ScannerAPIError(f"Polkadot Subscan request failed: {exc}") from exc
        except ValueError as exc:
            raise ScannerAPIError(f"Polkadot Subscan returned invalid JSON: {exc}") from exc

        if isinstance(payload, dict) and payload.get("code") not in (0, None):
            raise ScannerAPIError(f"Polkadot Subscan error: {payload.get('message') or payload}")

        data = (payload.get("data") or {}) if isinstance(payload, dict) else {}
        blocks = data.get("blocks") or []
        if not isinstance(blocks, list):
            blocks = []
        now = datetime.now(timezone.utc)
        samples: list[CapturedBlock] = []
        for b in blocks:
            if not isinstance(b, dict):
                continue
            fee = b.get("total_fee") or b.get("fee") or 0
            try:
                fee_val = Decimal(str(fee))
            except Exception:
                fee_val = Decimal("0")
            ts = now
            if b.get("block_timestamp"):
                try:
                    ts = datetime.fromtimestamp(int(b["block_timestamp"]), tz=timezone.utc)
                except Exception:
                    ts = now
            try:
                block_num = int(b.get("block_num", 0))
            except Exception:
                block_num = 0
            samples.append(CapturedBlock(number=block_num, timestamp=ts, fee_gwei=fee_val))
        if not samples:
            samples = [CapturedBlock(number=0, timestamp=now, fee_gwei=Decimal("0"))]
        return samples[: max(1, int(sample_size))]


class ChainlinkCatcher(BaseExternalCatcher):
    """Configurable Chainlink fee/sample catcher.

    Chainlink is not a native gas chain; this catcher records a configured or
    externally sourced metric value (default 0) to keep automation jobs safe and
    deterministic when no dedicated Chainlink fee endpoint is configured.
    """

    blockchain_name = "Chainlink"
    blockchain_symbol = "LINK"
    env_prefix = "CHAINLINK"
    default_api_url = "https://chain.link"
    default_api_key = ""

    def fetch_fee_samples(self, seconds: int, sample_size: int = 5) -> list[CapturedBlock]:
        now = datetime.now(timezone.utc)
        # No reliable public "gas fee" endpoint; return a stable zero-valued sample.
        # Configure a custom integration by subclassing if real fee data is needed.
        count = max(1, int(sample_size))
        step = max(1, int(seconds) // count)
        return [
            CapturedBlock(number=i + 1, timestamp=now - timedelta(seconds=i * step), fee_gwei=Decimal("0"))
            for i in range(count)
        ]


bitcoin_catcher = BitcoinMempoolCatcher()
solana_catcher = SolanaCatcher()
polkadot_catcher = PolkadotCatcher()
chainlink_catcher = ChainlinkCatcher()

__all__ = [
    "BaseExternalCatcher",
    "BitcoinMempoolCatcher",
    "SolanaCatcher",
    "PolkadotCatcher",
    "ChainlinkCatcher",
    "bitcoin_catcher",
    "solana_catcher",
    "polkadot_catcher",
    "chainlink_catcher",
]
