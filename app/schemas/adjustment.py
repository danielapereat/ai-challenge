from datetime import datetime, date
from decimal import Decimal
from typing import Literal, Optional
from pydantic import BaseModel, Field


class AdjustmentBase(BaseModel):
    adjustment_id: str = Field(..., description="Unique adjustment ID")
    transaction_reference: Optional[str] = Field(None, description="Reference to original transaction")
    amount: Decimal = Field(..., ge=0, description="Adjustment amount")
    currency: str = Field(..., min_length=3, max_length=3, description="Currency")
    type: Literal["refund", "chargeback"] = Field(..., description="Type: refund | chargeback")
    date: date = Field(..., description="Adjustment date")
    reason_code: Optional[str] = Field(None, description="Reason code")


class AdjustmentCreate(AdjustmentBase):
    pass


class AdjustmentResponse(AdjustmentBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdjustmentIngest(BaseModel):
    adjustments: list[AdjustmentCreate]
