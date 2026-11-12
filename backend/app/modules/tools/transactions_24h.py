from __future__ import annotations

import copy
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from app.exception import InvalidToolInputError, ScannerAPIError, UnsupportedBlockchainError


@dataclass
class ChainMetricResult:
    blockchain: str
    metric: str
    value: Any
    unit: str | None
    source: str
    fetched_at: str
    details: dict[str, Any] | None = None


_CACHE_TTL_SECONDS = 60.0
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_json(url: str, *, params: dict | None = None, timeout: float = 10.0) -> Any:
    try:
        response = requests.get(url, params=params, timeout=timeout, headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise ScannerAPIError(f"External request failed for {url}: {exc}") from exc
    except ValueError as exc:
        raise ScannerAPIError(f"External API returned invalid JSON for {url}: {exc}") from exc


def _normalize_chain(blockchain: str) -> str:
    return blockchain.strip().lower()


def _cache_get(key: str) -> dict[str, Any] | None:
    entry = _CACHE.get(key)
    if entry is None:
        return None
    expires_at, value = entry
    if expires_at <= time.monotonic():
        _CACHE.pop(key, None)
        return None
    cached = copy.deepcopy(value)
    cached["cached"] = True
    return cached


def _cache_set(key: str, value: dict[str, Any]) -> None:
    _CACHE[key] = (time.monotonic() + _CACHE_TTL_SECONDS, copy.deepcopy(value))


def get_transactions_last_24h(blockchain: str) -> dict[str, Any]:
    """Return an estimated transaction count over the last 24 hours for a blockchain."""
    raw_blockchain = blockchain.strip()
    key = raw_blockchain.lower()
    if not key:
        raise InvalidToolInputError("blockchain must not be empty")
    cache_key = f"transactions_24h:{key}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if key in {"bitcoin", "btc"}:
        blocks = _get_json("https://mempool.space/api/v1/blocks")
        now_ts = datetime.now(timezone.utc).timestamp()
        cutoff = now_ts - 24 * 3600
        tx_count = 0
        counted = 0
        if isinstance(blocks, list):
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                ts = b.get("timestamp")
                try:
                    ts_i = int(ts)
                except Exception:
                    continue
                if ts_i < cutoff:
                    continue
                try:
                    tx_count += int(b.get("tx_count", 0) or 0)
                except Exception:
                    pass
                counted += 1
        result = ChainMetricResult(
            blockchain="Bitcoin",
            metric="transactions_last_24h",
            value=tx_count,
            unit="transactions",
            source="mempool.space",
            fetched_at=_now_iso(),
            details={"blocks_counted": counted, "window_seconds": 86400, "approximate": True},
        )
        payload = asdict(result)
        _cache_set(cache_key, payload)
        return payload

    if key in {"solana", "sol"}:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getRecentPerformanceSamples",
            "params": [720],
        }
        try:
            resp = requests.post("https://api.mainnet-beta.solana.com", json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise ScannerAPIError(f"Solana RPC request failed: {exc}") from exc
        except ValueError as exc:
            raise ScannerAPIError(f"Solana RPC returned invalid JSON: {exc}") from exc
        samples = data.get("result") if isinstance(data, dict) else None
        total_tx = 0
        total_seconds = 0
        if isinstance(samples, list):
            for s in samples:
                if not isinstance(s, dict):
                    continue
                try:
                    total_tx += int(s.get("numTransactions", 0) or 0)
                    total_seconds += int(s.get("samplePeriodSecs", 0) or 0)
                except Exception:
                    continue
        value = total_tx
        approx = True
        if 0 < total_seconds < 86400:
            value = int(total_tx * (86400 / total_seconds))
        elif total_seconds >= 86400:
            value = int(total_tx * (86400 / total_seconds))
        result = ChainMetricResult(
            blockchain="Solana",
            metric="transactions_last_24h",
            value=value,
            unit="transactions",
            source="solana-rpc",
            fetched_at=_now_iso(),
            details={
                "samples": len(samples) if isinstance(samples, list) else 0,
                "sampled_seconds": total_seconds,
                "approximate": approx,
            },
        )
        payload_out = asdict(result)
        _cache_set(cache_key, payload_out)
        return payload_out

    evm_sources = {
        "ethereum": ("Ethereum", "https://api.etherscan.io/api", "ETHERSCAN_API_KEY"),
        "eth": ("Ethereum", "https://api.etherscan.io/api", "ETHERSCAN_API_KEY"),
        "polygon": ("Polygon", "https://api.polygonscan.com/api", "POLYGONSCAN_API_KEY"),
        "pol": ("Polygon", "https://api.polygonscan.com/api", "POLYGONSCAN_API_KEY"),
        "bnb smart chain": ("BNB Smart Chain", "https://api.bscscan.com/api", "BSCSCAN_API_KEY"),
        "bnb chain": ("BNB Smart Chain", "https://api.bscscan.com/api", "BSCSCAN_API_KEY"),
        "bsc": ("BNB Smart Chain", "https://api.bscscan.com/api", "BSCSCAN_API_KEY"),
        "bnb": ("BNB Smart Chain", "https://api.bscscan.com/api", "BSCSCAN_API_KEY"),
        "arbitrum": ("Arbitrum", "https://api.arbiscan.io/api", "ARBISCAN_API_KEY"),
        "arb": ("Arbitrum", "https://api.arbiscan.io/api", "ARBISCAN_API_KEY"),
        "avalanche": ("Avalanche", "https://api.snowtrace.io/api", "SNOWTRACE_API_KEY"),
        "avax": ("Avalanche", "https://api.snowtrace.io/api", "SNOWTRACE_API_KEY"),
    }
    if key in evm_sources:
        import os

        chain_name, api_url, key_env = evm_sources[key]
        params = {"module": "proxy", "action": "eth_blockNumber"}
        api_key = os.getenv(key_env, "")
        if api_key:
            params["apikey"] = api_key
        data = _get_json(api_url, params=params)
        latest_hex = data.get("result") if isinstance(data, dict) else None
        details: dict[str, Any] = {
            "approximate": True,
            "note": "Direct 24h transaction totals require chain-specific indexer/stats APIs or API keys; live latest block was fetched as a connectivity signal.",
        }
        if isinstance(latest_hex, str) and latest_hex.startswith("0x"):
            try:
                details["latest_block_number"] = int(latest_hex, 16)
            except Exception:
                pass
        result = ChainMetricResult(
            blockchain=chain_name,
            metric="transactions_last_24h",
            value=None,
            unit="transactions",
            source=api_url,
            fetched_at=_now_iso(),
            details=details,
        )
        payload_out = asdict(result)
        _cache_set(cache_key, payload_out)
        return payload_out

    raise UnsupportedBlockchainError(f"Unsupported blockchain for 24h transactions: {blockchain!r}")


__all__ = ["get_transactions_last_24h", "ChainMetricResult"]
