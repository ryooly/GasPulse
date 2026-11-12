from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.blockchains import Blockchain
from app.models.fee_chart_models import FeeChartData
from app.models.time_unit_models import TimeUnit, TimeUnitName


class FeeChartRepository:

    def __init__(self, session: Session) -> None:
        self._session = session

    def blockchain_exists(self, blockchain_name: str) -> bool:
        normalized = blockchain_name.strip().lower()
        if not normalized:
            return False
        stmt = select(Blockchain.id).where(func.lower(Blockchain.name) == normalized).limit(1)
        return self._session.scalar(stmt) is not None

    def list_latest_points(
        self,
        blockchain_name: str,
        time_unit: TimeUnitName,
        limit: int,
    ) -> list[FeeChartData]:
        normalized = blockchain_name.strip().lower()
        stmt = (
            select(FeeChartData)
            .join(Blockchain, FeeChartData.blockchain_id == Blockchain.id)
            .join(TimeUnit, FeeChartData.time_unit_id == TimeUnit.id)
            .where(func.lower(Blockchain.name) == normalized)
            .where(TimeUnit.name == time_unit)
            .options(
                selectinload(FeeChartData.blockchain),
                selectinload(FeeChartData.time_unit),
            )
            .order_by(FeeChartData.recorded_at.desc(), FeeChartData.id.desc())
            .limit(limit)
        )
        points = list(self._session.scalars(stmt).all())
        points.reverse()
        return points


__all__ = ["FeeChartRepository"]

