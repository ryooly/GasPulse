

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.fee_snapshot_models import FeeStatus

class BlockchainBase(BaseModel):
    """Fields shared by all blockchain representations."""

    name: str = Field(
        ..., min_length=1, max_length=100,
    )
    symbol: str = Field(
        ..., min_length=1, max_length=20,
    )
    chain_id: int | None = Field(
        None, ge=0, 
    )
    native_currency: str = Field(
        ..., min_length=1, max_length=50,
    )
    explorer_api_url: str | None = Field(
        None, max_length=255, 
    )
    is_active: bool = Field(
        True, 
    )

    @field_validator("name", "symbol", "native_currency", "explorer_api_url")
    @classmethod
    def _strip_whitespace(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("symbol")
    @classmethod
    def _upper_symbol(cls, value: str) -> str:
        return value.upper()


class BlockchainCreate(BlockchainBase):


class BlockchainUpdate(BaseModel):

    name: str | None = Field(None, min_length=1, max_length=100)
    symbol: str | None = Field(None, min_length=1, max_length=20)
    chain_id: int | None = Field(None, ge=0)
    native_currency: str | None = Field(None, min_length=1, max_length=50)
    explorer_api_url: str | None = Field(None, max_length=255)
    is_active: bool | None = None

    @field_validator("name", "symbol", "native_currency", "explorer_api_url")
    @classmethod
    def _strip_whitespace(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("symbol")
    @classmethod
    def _upper_symbol(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value


class BlockchainRead(BlockchainBase):

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


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


__all__ = [
    "BlockchainBase",
    "BlockchainCreate",
    "BlockchainRead",
    "BlockchainUpdate",
    "FeeSnapshotBase",
    "FeeSnapshotCreate",
    "FeeSnapshotRead",
    "FeeSnapshotUpdate",
]
