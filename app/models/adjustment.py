import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, DateTime, Numeric, Date, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Adjustment(Base):
    __tablename__ = "adjustments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    adjustment_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3))
    type: Mapped[str] = mapped_column(String(20))  # refund | chargeback
    date: Mapped[date] = mapped_column(Date)
    reason_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
