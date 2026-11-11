from __future__ import annotations

from app.exception import BlockchainNotFoundError, InvalidChartRangeError
from app.models.fee_chart_models import FeeChartData
from app.models.time_unit_models import TimeUnitName
from app.modules.repository import FeeChartRepository
from app.modules.tools import (
    get_token_price_usdt,
    get_transactions_last_24h,
    get_validators_last_24h,
)


class FeeChartService:

    ALLOWED_RANGES: dict[TimeUnitName, tuple[int, ...]] = {
        TimeUnitName.HOUR: (24, 48, 72),
        TimeUnitName.DAY: (7, 14, 21),
        TimeUnitName.WEEK: (3, 6, 9),
    }

    def __init__(self, repository: FeeChartRepository | None = None) -> None:
        self._repository = repository

    def allowed_ranges(self, time_unit: TimeUnitName) -> tuple[int, ...]:
        return self.ALLOWED_RANGES[time_unit]

    def get_chart(
        self,
        blockchain_name: str,
        time_unit: TimeUnitName,
        range_: int,
    ) -> list[FeeChartData]:
        if self._repository is None:
            raise RuntimeError("FeeChartRepository is required for chart operations")
        normalized_name = blockchain_name.strip()
        if not normalized_name:
            raise BlockchainNotFoundError("blockchain must not be empty")
        allowed = self.ALLOWED_RANGES[time_unit]
        if range_ not in allowed:
            raise InvalidChartRangeError(time_unit, range_, allowed)
        if not self._repository.blockchain_exists(normalized_name):
            raise BlockchainNotFoundError(f"Blockchain {normalized_name!r} was not found")
        return self._repository.list_latest_points(
            normalized_name, time_unit, limit=range_,
        )

    def get_token_price(self, token: str) -> dict:
        return get_token_price_usdt(token)

    def get_transactions_24h(self, blockchain_name: str) -> dict:
        return get_transactions_last_24h(blockchain_name)

    def get_validators_24h(self, blockchain_name: str) -> dict:
        return get_validators_last_24h(blockchain_name)


__all__ = ["FeeChartService", "InvalidChartRangeError"]

