from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import requests

from app.modules.automation.blockchain_catcher.base_catcher import (
    BaseBlockchainCatcher,
    ScannerAPIError,
)

# ==============================================================================
# Arbiscan Scanner Configuration & Placeholders
# ==============================================================================
# Replace these placeholders with your actual Arbiscan API URL and API key,
# or provide them via environment variables.
ARBISCAN_API_URL: str = os.getenv(
    "ARBISCAN_API_URL",
    "https://api.arbiscan.io/api",
)
ARBISCAN_API_KEY: str = os.getenv(
    "ARBISCAN_API_KEY",
    "YOUR_ARBISCAN_API_KEY",
)


class ArbiscanCatcher(BaseBlockchainCatcher):
    """Blockchain catcher for Arbitrum using Arbiscan API.

    Captures blocks within a specified timeframe (HOURS/DAYS/WEEKS)
    and inserts computed gas fee snapshots into the database table.
    """

    BLOCKCHAIN_NAME: str = "Arbitrum"
    BLOCKCHAIN_SYMBOL: str = "ARB"
    CHAIN_ID: int = 42161
    NATIVE_CURRENCY: str = "ETH"
    DEFAULT_API_URL: str = ARBISCAN_API_URL
    DEFAULT_API_KEY: str = ARBISCAN_API_KEY
    DEFAULT_USD_PRICE: Decimal = Decimal("2500")

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 15.0,
        default_usd_price: Decimal | None = None,
    ) -> None:
        super().__init__(
            api_url=api_url or ARBISCAN_API_URL,
            api_key=api_key or ARBISCAN_API_KEY,
            session=session,
            timeout=timeout,
            blockchain_name=self.BLOCKCHAIN_NAME,
            blockchain_symbol=self.BLOCKCHAIN_SYMBOL,
            chain_id=self.CHAIN_ID,
            native_currency=self.NATIVE_CURRENCY,
            default_usd_price=default_usd_price or self.DEFAULT_USD_PRICE,
        )

    def get_gas_oracle(self) -> dict[str, Any]:
        """Fetch current gas price estimates directly from Arbiscan gas oracle."""
        params = {
            "module": "gastracker",
            "action": "gasoracle",
        }
        data = self.make_scanner_request(params)
        if data.get("status") == "1" and "result" in data:
            return data["result"]
        raise ScannerAPIError(f"Failed to query Arbiscan gas oracle: {data}")


__all__ = ["ARBISCAN_API_KEY", "ARBISCAN_API_URL", "ArbiscanCatcher"]
