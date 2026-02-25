import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, DateTime, Numeric, Date, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    settlement_reference: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    gross_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    settlement_date: Mapped[date] = mapped_column(Date)
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    fees_deducted: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    bank_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
