from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class SettlementBase(BaseModel):
    settlement_reference: str = Field(..., description="Bank reference")
    amount: Decimal = Field(..., ge=0, description="Settled amount after fees")
    gross_amount: Optional[Decimal] = Field(None, ge=0, description="Original amount before fees")
    currency: str = Field(..., min_length=3, max_length=3, description="Settlement currency")
    settlement_date: date = Field(..., description="Settlement date")
    transaction_reference: Optional[str] = Field(None, description="Reference to original transaction")
    fees_deducted: Decimal = Field(default=Decimal("0"), ge=0, description="Fee amount")
    bank_name: str = Field(..., description="Originating bank")


class SettlementCreate(SettlementBase):
    pass


class SettlementResponse(SettlementBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class SettlementIngest(BaseModel):
    settlements: list[SettlementCreate]
