from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.blockchains import Blockchain
    from app.models.time_unit_models import TimeUnit


class FeeStatus(str, enum.Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"

class FeeSnapshot(Base):

    __tablename__ = "fee_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    blockchain_id: Mapped[int] = mapped_column(
        ForeignKey("blockchains.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    time_unit_id: Mapped[int] = mapped_column(
        ForeignKey("time_units.id", ondelete="RESTRICT"), nullable=False, index=True,
    )
    raw_fee_value: Mapped[Decimal] = mapped_column(
        Numeric(38, 18), nullable=False,
    )
    usd_value: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 8), nullable=True, 
    )
    avg_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(38, 18), nullable=True, 
    )
    median_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(38, 18), nullable=True,
    )
    min_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(38, 18), nullable=True,
    )
    max_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(38, 18), nullable=True,
    )
    sample_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    previous_value: Mapped[Decimal | None] = mapped_column(
        Numeric(38, 18), nullable=True,
    )
    status: Mapped[FeeStatus] = mapped_column(
        Enum(
            FeeStatus,
            native_enum=False,
            length=10,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=FeeStatus.STABLE,
    )
    change_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4), nullable=True,
    )
    block_number: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
    )

    blockchain: Mapped[Blockchain] = relationship(back_populates="fee_snapshots")
    time_unit: Mapped[TimeUnit] = relationship(back_populates="fee_snapshots")

    def __repr__(self) -> str: 
        return (
            f"<FeeSnapshot id={self.id} blockchain_id={self.blockchain_id} "
            f"time_unit_id={self.time_unit_id} "
            f"status={self.status.value!r} recorded_at={self.recorded_at!r}>"
        )


__all__ = ["FeeSnapshot", "FeeStatus"]
