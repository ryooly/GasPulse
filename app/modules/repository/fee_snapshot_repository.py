from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.blockchains import Blockchain
from app.models.fee_snapshot_models import FeeSnapshot
from app.models.time_unit_models import TimeUnit, TimeUnitName


class FeeSnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_latest_by_blockchain_and_time_unit(
        self,
        blockchain_name: str,
        time_unit: TimeUnitName,
    ) -> FeeSnapshot | None:
        stmt = (
            select(FeeSnapshot)
            .join(Blockchain, FeeSnapshot.blockchain_id == Blockchain.id)
            .join(TimeUnit, FeeSnapshot.time_unit_id == TimeUnit.id)
            .where(func.lower(Blockchain.name) == blockchain_name.strip().lower())
            .where(TimeUnit.name == time_unit)
            .options(
                selectinload(FeeSnapshot.blockchain),
                selectinload(FeeSnapshot.time_unit),
            )
            .order_by(FeeSnapshot.recorded_at.desc())
            .limit(1)
        )
        return self._session.scalars(stmt).first()


__all__ = ["FeeSnapshotRepository"]



# kita akan menambahkan semacam table baru untuk menyimpan setiap input sehingga itu akan memebtnuk semacam chart