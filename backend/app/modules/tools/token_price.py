from __future__ import annotations

import copy
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from app.exception import InvalidToolInputError, ScannerAPIError

COINGECKO_SIMPLE_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_SEARCH_URL = "https://api.coingecko.com/api/v3/search"

_TOKEN_ID_ALIASES: dict[str, str] = {
    "btc": "bitcoin",
    "bitcoin": "bitcoin",
    "eth": "ethereum",
    "ethereum": "ethereum",
    "bnb": "binancecoin",
    "binancecoin": "binancecoin",
    "matic": "matic-network",
    "polygon": "matic-network",
    "pol": "matic-network",
    "sol": "solana",
    "solana": "solana",
    "avax": "avalanche-2",
    "avalanche": "avalanche-2",
    "arb": "arbitrum",
    "arbitrum": "arbitrum",
    "op": "optimism",
    "optimism": "optimism",
    "dot": "polkadot",
    "polkadot": "polkadot",
    "link": "chainlink",
    "chainlink": "chainlink",
    "usdt": "tether",
    "tether": "tether",
}

_CACHE_TTL_SECONDS = 60.0
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


@dataclass
class TokenPriceResult:
    token: str
    coin_id: str
    price_usdt: float
    source: str
    fetched_at: str


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


def _resolve_coingecko_id(token: str) -> str:
    key = token.strip().lower()
    if not key:
        raise InvalidToolInputError("token must not be empty")
    if key in _TOKEN_ID_ALIASES:
        return _TOKEN_ID_ALIASES[key]
    data = _get_json(COINGECKO_SEARCH_URL, params={"query": token.strip()})
    coins = data.get("coins") if isinstance(data, dict) else None
    if isinstance(coins, list):
        token_lower = token.strip().lower()
        for coin in coins:
            if not isinstance(coin, dict):
                continue
            cid = str(coin.get("id", "")).lower()
            sym = str(coin.get("symbol", "")).lower()
            name = str(coin.get("name", "")).lower()
            if token_lower in {cid, sym, name}:
                return str(coin["id"])
        for coin in coins:
            if isinstance(coin, dict) and coin.get("id"):
                return str(coin["id"])
    return key


def get_token_price_usdt(token: str) -> dict[str, Any]:
    """Return the current price of a token quoted in USDT."""
    raw_token = token.strip()
    if not raw_token:
        raise InvalidToolInputError("token must not be empty")
    cache_key = f"token_price:{raw_token.lower()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    coin_id = _resolve_coingecko_id(raw_token)
    data = _get_json(
        COINGECKO_SIMPLE_PRICE_URL,
        params={"ids": coin_id, "vs_currencies": "usd,usdt"},
    )
    if not isinstance(data, dict) or coin_id not in data or not isinstance(data.get(coin_id), dict):
        raise ScannerAPIError(f"Could not resolve price for token {raw_token!r} (coin_id={coin_id!r})")
    prices = data[coin_id]
    price = prices.get("usdt", prices.get("usd"))
    if price is None:
        raise ScannerAPIError(f"No USDT/USD price available for token {raw_token!r} (coin_id={coin_id!r})")
    result = TokenPriceResult(
        token=raw_token,
        coin_id=coin_id,
        price_usdt=float(price),
        source="coingecko",
        fetched_at=_now_iso(),
    )
    payload = asdict(result)
    _cache_set(cache_key, payload)
    return payload


__all__ = ["get_token_price_usdt", "TokenPriceResult"]
