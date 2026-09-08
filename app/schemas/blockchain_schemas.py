from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator




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
    pass


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

__all__ = [
    "BlockchainBase",
    "BlockchainCreate",
    "BlockchainRead",
    "BlockchainUpdate",
]