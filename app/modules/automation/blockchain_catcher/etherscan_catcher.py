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
# Etherscan Scanner Configuration & Placeholders
# ==============================================================================
# Replace these placeholders with your actual Etherscan API URL and API key,
# or provide them via environment variables.
ETHERSCAN_API_URL: str = os.getenv(
    "ETHERSCAN_API_URL",
    "https://api.etherscan.io/api",
)
ETHERSCAN_API_KEY: str = os.getenv(
    "ETHERSCAN_API_KEY",
    "YOUR_ETHERSCAN_API_KEY",
)


class EtherscanCatcher(BaseBlockchainCatcher):
    """Blockchain catcher for Ethereum using Etherscan API.

    Captures blocks within a specified timeframe (HOURS/DAYS/WEEKS)
    and inserts computed gas fee snapshots into the database table.
    """

    BLOCKCHAIN_NAME: str = "Ethereum"
    BLOCKCHAIN_SYMBOL: str = "ETH"
    CHAIN_ID: int = 1
    NATIVE_CURRENCY: str = "ETH"
    DEFAULT_API_URL: str = ETHERSCAN_API_URL
    DEFAULT_API_KEY: str = ETHERSCAN_API_KEY
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
            api_url=api_url or ETHERSCAN_API_URL,
            api_key=api_key or ETHERSCAN_API_KEY,
            session=session,
            timeout=timeout,
            blockchain_name=self.BLOCKCHAIN_NAME,
            blockchain_symbol=self.BLOCKCHAIN_SYMBOL,
            chain_id=self.CHAIN_ID,
            native_currency=self.NATIVE_CURRENCY,
            default_usd_price=default_usd_price or self.DEFAULT_USD_PRICE,
        )

    def get_gas_oracle(self) -> dict[str, Any]:
        """Fetch current gas price estimates directly from Etherscan gas oracle."""
        params = {
            "module": "gastracker",
            "action": "gasoracle",
        }
        data = self.make_scanner_request(params)
        if data.get("status") == "1" and "result" in data:
            return data["result"]
        raise ScannerAPIError(f"Failed to query Etherscan gas oracle: {data}")


__all__ = ["ETHERSCAN_API_KEY", "ETHERSCAN_API_URL", "EtherscanCatcher"]
