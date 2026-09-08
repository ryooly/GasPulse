from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.fee_snapshot_models import FeeSnapshot


class TimeUnitName(str, enum.Enum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"


class TimeUnit(Base):

    __tablename__ = "time_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[TimeUnitName] = mapped_column(
        Enum(
            TimeUnitName,
            native_enum=False,
            length=10,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        unique=True,
        index=True,
    )
    interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow,
    )

    fee_snapshots: Mapped[list[FeeSnapshot]] = relationship(
        back_populates="time_unit",
    )

    def __repr__(self) -> str:
        return (
            f"<TimeUnit id={self.id} name={self.name.value!r} "
            f"interval_seconds={self.interval_seconds}>"
        )


__all__ = ["TimeUnit", "TimeUnitName"]
