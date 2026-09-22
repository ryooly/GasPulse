from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.blockchains import Blockchain
    from app.models.time_unit_models import TimeUnit


class FeeChartData(Base):
    __tablename__ = "fee_chart_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    blockchain_id: Mapped[int] = mapped_column(
        ForeignKey("blockchains.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    time_unit_id: Mapped[int] = mapped_column(
        ForeignKey("time_units.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    fee_value: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
    )

    blockchain: Mapped[Blockchain] = relationship(back_populates="fee_chart_data")
    time_unit: Mapped[TimeUnit] = relationship(back_populates="fee_chart_data")

    __table_args__ = (
        Index("ix_fee_chart_data_point", "blockchain_id", "time_unit_id", "recorded_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<FeeChartData id={self.id} blockchain_id={self.blockchain_id} "
            f"time_unit_id={self.time_unit_id} recorded_at={self.recorded_at!r}>"
        )


__all__ = ["FeeChartData"]
