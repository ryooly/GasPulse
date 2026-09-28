from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import requests

from app.modules.automation.blockchain_catcher.base_catcher import (
    BaseBlockchainCatcher,
    ScannerAPIError,
)

BSCSCAN_API_URL: str = os.getenv(
    "BSCSCAN_API_URL",
    "https://api.bscscan.com/api",
)
BSCSCAN_API_KEY: str = os.getenv(
    "BSCSCAN_API_KEY",
    "YOUR_BSCSCAN_API_KEY",
)


class BscScanCatcher(BaseBlockchainCatcher):

    BLOCKCHAIN_NAME: str = "BNB Smart Chain"
    BLOCKCHAIN_SYMBOL: str = "BNB"
    CHAIN_ID: int = 56
    NATIVE_CURRENCY: str = "BNB"
    DEFAULT_API_URL: str = BSCSCAN_API_URL
    DEFAULT_API_KEY: str = BSCSCAN_API_KEY
    DEFAULT_USD_PRICE: Decimal = Decimal("600")

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
        session: requests.Session | None = None,
        timeout: float = 15.0,
        default_usd_price: Decimal | None = None,
    ) -> None:
        super().__init__(
            api_url=api_url or BSCSCAN_API_URL,
            api_key=api_key or BSCSCAN_API_KEY,
            session=session,
            timeout=timeout,
            blockchain_name=self.BLOCKCHAIN_NAME,
            blockchain_symbol=self.BLOCKCHAIN_SYMBOL,
            chain_id=self.CHAIN_ID,
            native_currency=self.NATIVE_CURRENCY,
            default_usd_price=default_usd_price or self.DEFAULT_USD_PRICE,
        )

    def get_gas_oracle(self) -> dict[str, Any]:
        params = {
            "module": "gastracker",
            "action": "gasoracle",
        }
        data = self.make_scanner_request(params)
        if data.get("status") == "1" and "result" in data:
            return data["result"]
        raise ScannerAPIError(f"Failed to query BscScan gas oracle: {data}")


__all__ = ["BSCSCAN_API_KEY", "BSCSCAN_API_URL", "BscScanCatcher"]
