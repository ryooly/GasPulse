from __future__ import annotations
from tracemalloc import Snapshot

from app.models.time_unit_models import TimeUnitName
from app.schemas.fee_snapshot_schemas import FeeSnapshotPublic
from app.modules.service import FeeSnapshotService


class FeeSnapshotController:

    def __init__(self, service: FeeSnapshotService) -> None:
        self._service = service

    def get_fees(
        self,
        blockchain_name: str,
        time_unit: TimeUnitName,
    ) -> list[FeeSnapshotPublic]:
        snapshots = self._service.get_latest_valid(
            blockchain_name, time_unit,
        ) 
        return snapshots # tambahkan wwaktu untuk mengambil semau fees tanpa waktu acuan 

    def get_hourly_fees(self, blockchain_name: str) -> list[FeeSnapshotPublic]:
        return self._service.get_latest_valid(blockchain_name, TimeUnitName.HOUR)

    def get_daily_fees(self, blockchain_name: str) -> list[FeeSnapshotPublic]:
        return self._service.get_latest_valid(blockchain_name, TimeUnitName.DAY)

    def get_weekly_fees(self, blockchain_name: str) -> list[FeeSnapshotPublic]:
        return self._service.get_latest_valid(blockchain_name, TimeUnitName.WEEK)


__all__ = ["FeeSnapshotController"]
