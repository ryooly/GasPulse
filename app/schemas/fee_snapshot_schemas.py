

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import (
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.models.fee_snapshot_models import FeeStatus


class FeeSnapshotBase(BaseModel):

    blockchain_id: int = Field(
        ..., gt=0, 
    )
    raw_fee_value: Decimal = Field(
        ..., ge=0, 
    )
    usd_value: Decimal | None = Field(
        None, ge=0, 
    )
    avg_fee: Decimal | None = Field(None, ge=0)
    median_fee: Decimal | None = Field(
        None, ge=0
    )
    min_fee: Decimal | None = Field(None, ge=0)
    max_fee: Decimal | None = Field(None, ge=0)
    sample_count: int = Field(
        0, ge=0,
    )
    previous_value: Decimal | None = Field(
        None, ge=0,
    )
    status: FeeStatus = Field(
        FeeStatus.STABLE,
    )
    change_percentage: Decimal | None = Field(
        None,
    )
    block_number: int | None = Field(
        None, ge=0,
    )
    recorded_at: datetime = Field(
        ...,
    )

    @model_validator(mode="after")
    def _validate_fee_range(self) -> FeeSnapshotBase:
        if self.min_fee is not None and self.max_fee is not None and self.min_fee > self.max_fee:
            raise ValueError("min_fee cannot be greater than max_fee")
        return self


class FeeSnapshotCreate(FeeSnapshotBase):
    pass


class FeeSnapshotUpdate(BaseModel):

    blockchain_id: int | None = Field(None, gt=0)
    raw_fee_value: Decimal | None = Field(None, ge=0)
    usd_value: Decimal | None = Field(None, ge=0)
    avg_fee: Decimal | None = Field(None, ge=0)
    median_fee: Decimal | None = Field(None, ge=0)
    min_fee: Decimal | None = Field(None, ge=0)
    max_fee: Decimal | None = Field(None, ge=0)
    sample_count: int | None = Field(None, ge=0)
    previous_value: Decimal | None = Field(None, ge=0)
    status: FeeStatus | None = None
    change_percentage: Decimal | None = None
    block_number: int | None = Field(None, ge=0)
    recorded_at: datetime | None = None


class FeeSnapshotRead(FeeSnapshotBase):

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class FeeSnapshotPublic(BaseModel):
    """User-facing fee snapshot returned by the public fee endpoints.

    Mirrors the full ``FeeSnapshot`` payload for the frontend but drops
    internal-only fields that should never be shown to users (``created_at``
    and the raw ``blockchain_id`` / ``time_unit_id`` foreign keys). The related
    blockchain and time-unit names are surfaced instead of their ids.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    blockchain_name: str = Field(
        validation_alias=AliasPath("blockchain", "name"),
    )
    time_unit: str = Field(
        validation_alias=AliasPath("time_unit", "name"),
    )
    raw_fee_value: Decimal
    usd_value: Decimal | None = None
    avg_fee: Decimal | None = None
    median_fee: Decimal | None = None
    min_fee: Decimal | None = None
    max_fee: Decimal | None = None
    sample_count: int
    previous_value: Decimal | None = None
    status: FeeStatus
    change_percentage: Decimal | None = None
    block_number: int | None = None
    recorded_at: datetime


__all__ = [
    "FeeSnapshotBase",
    "FeeSnapshotCreate",
    "FeeSnapshotPublic",
    "FeeSnapshotRead",
    "FeeSnapshotUpdate",
]
