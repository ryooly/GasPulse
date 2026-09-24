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
# Snowtrace (Avalanche) Scanner Configuration & Placeholders
# ==============================================================================
# Replace these placeholders with your actual Snowtrace API URL and API key,
# or provide them via environment variables.
SNOWTRACE_API_URL: str = os.getenv(
    "SNOWTRACE_API_URL",
    "https://api.snowtrace.io/api",
)
SNOWTRACE_API_KEY: str = os.getenv(
    "SNOWTRACE_API_KEY",
    "YOUR_SNOWTRACE_API_KEY",
)


class SnowtraceCatcher(BaseBlockchainCatcher):
    """Blockchain catcher for Avalanche (C-Chain) using Snowtrace API.

    Captures blocks within a specified timeframe (HOURS/DAYS/WEEKS)
    and inserts computed gas fee snapshots into the database table.
    """

    BLOCKCHAIN_NAME: str = "Avalanche"
    BLOCKCHAIN_SYMBOL: str = "AVAX"
    CHAIN_ID: int = 43114
    NATIVE_CURRENCY: str = "AVAX"
    DEFAULT_API_URL: str = SNOWTRACE_API_URL
    DEFAULT_API_KEY: str = SNOWTRACE_API_KEY
    DEFAULT_USD_PRICE: Decimal = Decimal("30")

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 15.0,
        default_usd_price: Decimal | None = None,
    ) -> None:
        super().__init__(
            api_url=api_url or SNOWTRACE_API_URL,
            api_key=api_key or SNOWTRACE_API_KEY,
            session=session,
            timeout=timeout,
            blockchain_name=self.BLOCKCHAIN_NAME,
            blockchain_symbol=self.BLOCKCHAIN_SYMBOL,
            chain_id=self.CHAIN_ID,
            native_currency=self.NATIVE_CURRENCY,
            default_usd_price=default_usd_price or self.DEFAULT_USD_PRICE,
        )

    def get_gas_oracle(self) -> dict[str, Any]:
        """Fetch current gas price estimates directly from Snowtrace gas oracle."""
        params = {
            "module": "gastracker",
            "action": "gasoracle",
        }
        data = self.make_scanner_request(params)
        if data.get("status") == "1" and "result" in data:
            return data["result"]
        raise ScannerAPIError(f"Failed to query Snowtrace gas oracle: {data}")


__all__ = ["SNOWTRACE_API_KEY", "SNOWTRACE_API_URL", "SnowtraceCatcher"]
