from __future__ import annotations

import enum
from datetime import datetime, timezone
from decimal import Decimal

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
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.models.blockchain_models import 


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):


class FeeStatus(str, enum.Enum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


class Blockchain(Base):

    __tablename__ = "blockchains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True,
    )
    symbol: Mapped[str] = mapped_column(
        String(20), nullable=False, unique=True, index=True,
    )
    chain_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    native_currency: Mapped[str] = mapped_column(
        String(50), nullable=False,
    )
    explorer_api_url: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow,
    )

    fee_snapshots: Mapped[list[FeeSnapshot]] = relationship(
        back_populates="blockchain",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str: 
        return f"<Blockchain id={self.id} name={self.name!r} symbol={self.symbol!r}>"


class FeeSnapshot(Base):

    __tablename__ = "fee_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    blockchain_id: Mapped[int] = mapped_column(
        ForeignKey("blockchains.id", ondelete="CASCADE"), nullable=False, index=True,
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

    def __repr__(self) -> str: 
        return (
            f"<FeeSnapshot id={self.id} blockchain_id={self.blockchain_id} "
            f"status={self.status.value!r} recorded_at={self.recorded_at!r}>"
        )


__all__ = ["Base", "Blockchain", "FeeSnapshot", "FeeStatus", "utcnow"]
