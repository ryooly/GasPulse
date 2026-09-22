from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.blockchains import Blockchain
from app.models.fee_chart_models import FeeChartData
from app.models.time_unit_models import TimeUnit, TimeUnitName


class FeeChartRepository:

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_latest_points(
        self,
        blockchain_name: str,
        time_unit: TimeUnitName,
        limit: int,
    ) -> list[FeeChartData]:
        stmt = (
            select(FeeChartData)
            .join(Blockchain, FeeChartData.blockchain_id == Blockchain.id)
            .join(TimeUnit, FeeChartData.time_unit_id == TimeUnit.id)
            .where(func.lower(Blockchain.name) == blockchain_name.strip().lower())
            .where(TimeUnit.name == time_unit)
            .options(
                selectinload(FeeChartData.blockchain),
                selectinload(FeeChartData.time_unit),
            )
            .order_by(FeeChartData.recorded_at.desc())
            .limit(limit)
        )
        points = list(self._session.scalars(stmt).all())
        points.reverse()
        return points


__all__ = ["FeeChartRepository"]
