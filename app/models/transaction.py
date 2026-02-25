import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, DateTime, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    merchant_order_id: Mapped[str] = mapped_column(String(100), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20))  # authorized | captured | failed
    customer_id: Mapped[str] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(3))  # MX, CO, BR
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
