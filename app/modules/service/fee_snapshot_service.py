from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from app.models.fee_snapshot_models import FeeSnapshot
from app.models.time_unit_models import TimeUnitName
from app.modules.repository import FeeSnapshotRepository
from db.base import utcnow


class FeeSnapshotService:

    def __init__(
        self,
        repository: FeeSnapshotRepository,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def get_latest_valid(
        self,
        blockchain_name: str,
        time_unit: TimeUnitName,
    ) -> FeeSnapshot | None:

        snapshot = self._repository.get_latest_by_blockchain_and_time_unit(
            blockchain_name, time_unit,
        )
        if snapshot is None or not self._is_still_valid(snapshot):
            return None
        return snapshot

    def _is_still_valid(self, snapshot: FeeSnapshot) -> bool:
        age = self._clock() - self._as_utc(snapshot.recorded_at)
        return age.total_seconds() <= snapshot.time_unit.interval_seconds

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


__all__ = ["FeeSnapshotService"]
