import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import String, DateTime, Numeric, Integer, JSON, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("transactions.id"),
        nullable=True,
        index=True
    )
    settlement_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("settlements.id"),
        nullable=True,
        index=True
    )
    adjustment_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("adjustments.id"),
        nullable=True,
        index=True
    )
    match_type: Mapped[str] = mapped_column(String(50))  # transaction_settlement | transaction_adjustment
    confidence_score: Mapped[int] = mapped_column(Integer)  # 0-100
    match_reasons: Mapped[list] = mapped_column(JSON, default=list)
    amount_difference: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    date_difference_days: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20))  # matched | pending_review | unmatched
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    transaction = relationship("Transaction", foreign_keys=[transaction_id])
    settlement = relationship("Settlement", foreign_keys=[settlement_id])
    adjustment = relationship("Adjustment", foreign_keys=[adjustment_id])
