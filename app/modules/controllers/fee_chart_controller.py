from __future__ import annotations

from app.models.time_unit_models import TimeUnitName
from app.modules.service import FeeChartService
from app.schemas.fee_chart_schemas import FeeChartPointPublic


class FeeChartController:

    def __init__(self, service: FeeChartService) -> None:
        self._service = service

    def get_chart(
        self,
        blockchain_name: str,
        time_unit: TimeUnitName,
        range_: int,
    ) -> list[FeeChartPointPublic]:
        return self._service.get_chart(blockchain_name, time_unit, range_) # tambahkan charrt universal

    def get_hourly_chart(
        self, blockchain_name: str, range_: int,
    ) -> list[FeeChartPointPublic]:
        return self._service.get_chart(blockchain_name, TimeUnitName.HOUR, range_)

    def get_daily_chart(
        self, blockchain_name: str, range_: int,
    ) -> list[FeeChartPointPublic]:
        return self._service.get_chart(blockchain_name, TimeUnitName.DAY, range_)

    def get_weekly_chart(
        self, blockchain_name: str, range_: int,
    ) -> list[FeeChartPointPublic]:
        return self._service.get_chart(blockchain_name, TimeUnitName.WEEK, range_)


__all__ = ["FeeChartController"]
