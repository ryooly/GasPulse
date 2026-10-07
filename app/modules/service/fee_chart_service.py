from __future__ import annotations

from app.exception import InvalidChartRangeError
from app.models.fee_chart_models import FeeChartData
from app.models.time_unit_models import TimeUnitName
from app.modules.repository import FeeChartRepository


class FeeChartService:

    ALLOWED_RANGES: dict[TimeUnitName, tuple[int, ...]] = {
        TimeUnitName.HOUR: (24, 48, 72),
        TimeUnitName.DAY: (7, 14, 21),
        TimeUnitName.WEEK: (3, 6, 9),
    }

    def __init__(self, repository: FeeChartRepository) -> None:
        self._repository = repository

    def allowed_ranges(self, time_unit: TimeUnitName) -> tuple[int, ...]:
        return self.ALLOWED_RANGES[time_unit]

    def get_chart(
        self,
        blockchain_name: str,
        time_unit: TimeUnitName,
        range_: int,
    ) -> list[FeeChartData]:
        allowed = self.ALLOWED_RANGES[time_unit]
        if range_ not in allowed:
            raise InvalidChartRangeError(time_unit, range_, allowed)
        return self._repository.list_latest_points(
            blockchain_name, time_unit, limit=range_,
        )


__all__ = ["FeeChartService", "InvalidChartRangeError"]
