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


def get_validators_last_24h(blockchain: str) -> dict[str, Any]:
    """Return validator/consensus-participation info over the last 24 hours."""
    raw_blockchain = blockchain.strip()
    key = raw_blockchain.lower()
    if not key:
        raise InvalidToolInputError("blockchain must not be empty")
    cache_key = f"validators_24h:{key}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if key in {"solana", "sol"}:
        payload = {"jsonrpc": "2.0", "id": 1, "method": "getVoteAccounts", "params": []}
        try:
            resp = requests.post("https://api.mainnet-beta.solana.com", json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            raise ScannerAPIError(f"Solana RPC request failed: {exc}") from exc
        except ValueError as exc:
            raise ScannerAPIError(f"Solana RPC returned invalid JSON: {exc}") from exc
        res = data.get("result") if isinstance(data, dict) else {}
        current = res.get("current") if isinstance(res, dict) else []
        delinquent = res.get("delinquent") if isinstance(res, dict) else []
        current_n = len(current) if isinstance(current, list) else 0
        delinquent_n = len(delinquent) if isinstance(delinquent, list) else 0
        result = ChainMetricResult(
            blockchain="Solana",
            metric="validators_last_24h",
            value=current_n,
            unit="active_validators",
            source="solana-rpc",
            fetched_at=_now_iso(),
            details={
                "active_current": current_n,
                "delinquent": delinquent_n,
                "window": "current_vote_accounts",
                "approximate": True,
                "note": "Reports current active vote accounts as a proxy for validator participation.",
            },
        )
        payload_out = asdict(result)
        _cache_set(cache_key, payload_out)
        return payload_out

    if key in {"polkadot", "dot"}:
        import os

        base = os.getenv("POLKADOT_SUBSCAN_API_URL", "https://polkadot.api.subscan.io").rstrip("/")
        api_key = os.getenv("POLKADOT_SUBSCAN_API_KEY", "")
        if not api_key:
            result = ChainMetricResult(
                blockchain="Polkadot",
                metric="validators_last_24h",
                value=None,
                unit="validators",
                source=base,
                fetched_at=_now_iso(),
                details={
                    "approximate": True,
                    "note": "Set POLKADOT_SUBSCAN_API_KEY to query validator data from Subscan.",
                },
            )
            payload_out = asdict(result)
            _cache_set(cache_key, payload_out)
            return payload_out
        headers = {"Content-Type": "application/json", "X-API-Key": api_key}
        try:
            resp = requests.post(
                f"{base}/api/scan/staking/validators",
                json={"row": 1, "page": 0},
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as exc:
            raise ScannerAPIError(f"Polkadot Subscan request failed: {exc}") from exc
        except ValueError as exc:
            raise ScannerAPIError(f"Polkadot Subscan returned invalid JSON: {exc}") from exc
        data = payload.get("data") if isinstance(payload, dict) else {}
        count = data.get("count") if isinstance(data, dict) else None
        result = ChainMetricResult(
            blockchain="Polkadot",
            metric="validators_last_24h",
            value=count,
            unit="validators",
            source=base,
            fetched_at=_now_iso(),
            details={"approximate": True, "window": "current_validator_set"},
        )
        payload_out = asdict(result)
        _cache_set(cache_key, payload_out)
        return payload_out

    if key in {"bitcoin", "btc"}:
        pools = _get_json("https://mempool.space/api/v1/mining/pools/24h")
        pool_count = None
        blocks_mined = None
        if isinstance(pools, dict):
            pool_list = pools.get("pools")
            if isinstance(pool_list, list):
                pool_count = len(pool_list)
            try:
                blocks_mined = int(pools.get("blockCount")) if pools.get("blockCount") is not None else None
            except Exception:
                blocks_mined = None
        result = ChainMetricResult(
            blockchain="Bitcoin",
            metric="validators_last_24h",
            value=pool_count,
            unit="mining_pools",
            source="mempool.space",
            fetched_at=_now_iso(),
            details={
                "blocks_mined_24h": blocks_mined,
                "approximate": True,
                "note": "Bitcoin uses miners/pools; reports distinct mining pools active in last 24h as a proxy.",
            },
        )
        payload_out = asdict(result)
        _cache_set(cache_key, payload_out)
        return payload_out

    evm_names = {
        "ethereum": "Ethereum",
        "eth": "Ethereum",
        "polygon": "Polygon",
        "pol": "Polygon",
        "bnb smart chain": "BNB Smart Chain",
        "bsc": "BNB Smart Chain",
        "bnb": "BNB Smart Chain",
        "arbitrum": "Arbitrum",
        "arb": "Arbitrum",
        "avalanche": "Avalanche",
        "avax": "Avalanche",
    }
    if key in evm_names:
        result = ChainMetricResult(
            blockchain=evm_names[key],
            metric="validators_last_24h",
            value=None,
            unit="validators",
            source="n/a",
            fetched_at=_now_iso(),
            details={
                "approximate": True,
                "note": "Validator counts for this chain require beacon-chain/indexer APIs and are not derivable from standard gas scanner APIs.",
            },
        )
        payload_out = asdict(result)
        _cache_set(cache_key, payload_out)
        return payload_out

    raise UnsupportedBlockchainError(f"Unsupported blockchain for 24h validators: {blockchain!r}")


__all__ = ["get_validators_last_24h", "ChainMetricResult"]
