from __future__ import annotations

from app.models.time_unit_models import TimeUnitName
from app.modules.repository import FeeSnapshotRepository
from app.schemas.fee_snapshot_schemas import FeeSnapshotPublic


class FeeSnapshotController:

    def __init__(self, repository: FeeSnapshotRepository) -> None:
        self._repository = repository

    def get_fees(
        self,
        blockchain_name: str,
        time_unit: TimeUnitName,
    ) -> list[FeeSnapshotPublic]:
        snapshots = self._repository.list_by_blockchain_and_time_unit(
            blockchain_name, time_unit,
        ) # chnage use servie
        return 

    def get_hourly_fees(self, blockchain_name: str) -> list[FeeSnapshotPublic]:
        return self.get_fees(blockchain_name, TimeUnitName.HOUR)

    def get_daily_fees(self, blockchain_name: str) -> list[FeeSnapshotPublic]:
        return self.get_fees(blockchain_name, TimeUnitName.DAY)

    def get_weekly_fees(self, blockchain_name: str) -> list[FeeSnapshotPublic]:
        return self.get_fees(blockchain_name, TimeUnitName.WEEK)


__all__ = ["FeeSnapshotController"]
