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
# Polygonscan Scanner Configuration & Placeholders
# ==============================================================================
# Replace these placeholders with your actual Polygonscan API URL and API key,
# or provide them via environment variables.
POLYGONSCAN_API_URL: str = os.getenv(
    "POLYGONSCAN_API_URL",
    "https://api.polygonscan.com/api",
)
POLYGONSCAN_API_KEY: str = os.getenv(
    "POLYGONSCAN_API_KEY",
    "YOUR_POLYGONSCAN_API_KEY",
)


class PolygonscanCatcher(BaseBlockchainCatcher):
    """Blockchain catcher for Polygon (POL) using Polygonscan API.

    Captures blocks within a specified timeframe (HOURS/DAYS/WEEKS)
    and inserts computed gas fee snapshots into the database table.
    """

    BLOCKCHAIN_NAME: str = "Polygon"
    BLOCKCHAIN_SYMBOL: str = "POL"
    CHAIN_ID: int = 137
    NATIVE_CURRENCY: str = "POL"
    DEFAULT_API_URL: str = POLYGONSCAN_API_URL
    DEFAULT_API_KEY: str = POLYGONSCAN_API_KEY
    DEFAULT_USD_PRICE: Decimal = Decimal("0.50")

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 15.0,
        default_usd_price: Decimal | None = None,
    ) -> None:
        super().__init__(
            api_url=api_url or POLYGONSCAN_API_URL,
            api_key=api_key or POLYGONSCAN_API_KEY,
            session=session,
            timeout=timeout,
            blockchain_name=self.BLOCKCHAIN_NAME,
            blockchain_symbol=self.BLOCKCHAIN_SYMBOL,
            chain_id=self.CHAIN_ID,
            native_currency=self.NATIVE_CURRENCY,
            default_usd_price=default_usd_price or self.DEFAULT_USD_PRICE,
        )

    def get_gas_oracle(self) -> dict[str, Any]:
        """Fetch current gas price estimates directly from Polygonscan gas oracle."""
        params = {
            "module": "gastracker",
            "action": "gasoracle",
        }
        data = self.make_scanner_request(params)
        if data.get("status") == "1" and "result" in data:
            return data["result"]
        raise ScannerAPIError(f"Failed to query Polygonscan gas oracle: {data}")


__all__ = ["POLYGONSCAN_API_KEY", "POLYGONSCAN_API_URL", "PolygonscanCatcher"]
