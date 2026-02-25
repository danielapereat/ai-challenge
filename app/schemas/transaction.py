from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class TransactionBase(BaseModel):
    transaction_id: str = Field(..., description="Yuno transaction ID")
    merchant_order_id: str = Field(..., description="Merchant's order reference")
    amount: Decimal = Field(..., ge=0, description="Transaction amount")
    currency: str = Field(..., min_length=3, max_length=3, description="ISO currency code")
    timestamp: datetime = Field(..., description="Transaction timestamp")
    status: str = Field(..., description="Transaction status: authorized | captured | failed")
    customer_id: str = Field(..., description="Customer identifier")
    country: str = Field(..., min_length=2, max_length=3, description="Country code")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"authorized", "captured", "failed"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class TransactionCreate(TransactionBase):
    pass


class TransactionResponse(TransactionBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionIngest(BaseModel):
    transactions: list[TransactionCreate]


class IngestResponse(BaseModel):
    ingested: int
    errors: list[str] = []
