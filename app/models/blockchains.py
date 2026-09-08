from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, utcnow

if TYPE_CHECKING:
    from app.models.fee_snapshot_models import FeeSnapshot


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

__all__ = [
    "Blockchain",
]