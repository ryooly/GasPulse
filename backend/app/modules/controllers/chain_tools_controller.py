from __future__ import annotations

from app.modules.service import FeeChartService


class ChainToolsController:

    def __init__(self, service: FeeChartService) -> None:
        self._service = service

    def get_token_price(self, token: str) -> dict:
        return self._service.get_token_price(token)

    def get_transactions_24h(self, blockchain_name: str) -> dict:
        return self._service.get_transactions_24h(blockchain_name)

    def get_validators_24h(self, blockchain_name: str) -> dict:
        return self._service.get_validators_24h(blockchain_name)


__all__ = ["ChainToolsController"]
