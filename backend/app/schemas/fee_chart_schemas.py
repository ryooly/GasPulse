from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import AliasPath, BaseModel, ConfigDict, Field


class FeeChartPointPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    blockchain_name: str = Field(
        validation_alias=AliasPath("blockchain", "name"),
    )
    time_unit: str = Field(
        validation_alias=AliasPath("time_unit", "name"),
    )
    fee_value: Decimal
    recorded_at: datetime


__all__ = ["FeeChartPointPublic"]
