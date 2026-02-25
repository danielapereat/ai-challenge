from datetime import datetime
from datetime import date as date_type
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class AdjustmentBase(BaseModel):
    adjustment_id: str = Field(..., description="Unique adjustment ID")
    transaction_reference: Optional[str] = Field(None, description="Reference to original transaction")
    amount: Decimal = Field(..., ge=0, description="Adjustment amount")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency")
    type: str = Field(..., description="Type: refund | chargeback")
    date: date_type = Field(..., description="Adjustment date")
    reason_code: Optional[str] = Field(None, description="Reason code")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"refund", "chargeback"}
        if v not in allowed:
            raise ValueError(f"type must be one of {allowed}")
        return v


class AdjustmentCreate(AdjustmentBase):
    pass


class AdjustmentResponse(AdjustmentBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdjustmentIngest(BaseModel):
    adjustments: list[AdjustmentCreate]
