"""Service for querying match data and finding potential matches."""
from typing import Optional
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models import Transaction, Settlement, Adjustment, MatchResult
from app.config import settings


class MatchingService:
    """Service for querying matches and finding potential match candidates."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_match_by_id(self, match_id: str) -> Optional[MatchResult]:
        """Get a match result by ID."""
        result = await self.db.execute(
            select(MatchResult).where(MatchResult.id == match_id)
        )
        return result.scalar_one_or_none()

    async def get_transaction_by_id(self, transaction_id: str) -> Optional[Transaction]:
        """Get a transaction by ID (either internal or external ID)."""
        # Try internal ID first
        result = await self.db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        txn = result.scalar_one_or_none()
        if txn:
            return txn

        # Try external transaction_id
        result = await self.db.execute(
            select(Transaction).where(Transaction.transaction_id == transaction_id)
        )
        return result.scalar_one_or_none()

    async def get_settlement_by_id(self, settlement_id: str) -> Optional[Settlement]:
        """Get a settlement by ID (either internal or external ID)."""
        # Try internal ID first
        result = await self.db.execute(
            select(Settlement).where(Settlement.id == settlement_id)
        )
        stl = result.scalar_one_or_none()
        if stl:
            return stl

        # Try external settlement_id
        result = await self.db.execute(
            select(Settlement).where(Settlement.settlement_id == settlement_id)
        )
        return result.scalar_one_or_none()

    async def get_adjustment_by_id(self, adjustment_id: str) -> Optional[Adjustment]:
        """Get an adjustment by ID (either internal or external ID)."""
        # Try internal ID first
        result = await self.db.execute(
            select(Adjustment).where(Adjustment.id == adjustment_id)
        )
        adj = result.scalar_one_or_none()
        if adj:
            return adj

        # Try external adjustment_id
        result = await self.db.execute(
            select(Adjustment).where(Adjustment.adjustment_id == adjustment_id)
        )
        return result.scalar_one_or_none()

    async def find_potential_settlements(self, transaction_id: str) -> list[dict]:
        """Find potential settlement matches for a transaction."""
        transaction = await self.get_transaction_by_id(transaction_id)
        if not transaction:
            return []

        # Find settlements within tolerance
        tolerance = settings.AMOUNT_TOLERANCE_PERCENT / Decimal("100")
        min_amount = transaction.amount * (1 - tolerance)
        max_amount = transaction.amount * (1 + tolerance)

        result = await self.db.execute(
            select(Settlement).where(
                and_(
                    Settlement.currency == transaction.currency,
                    Settlement.amount >= min_amount,
                    Settlement.amount <= max_amount
                )
            ).limit(10)
        )
        settlements = result.scalars().all()

        return [
            {
                "id": stl.id,
                "settlement_id": stl.settlement_id,
                "amount": float(stl.amount),
                "currency": stl.currency,
                "date": str(stl.settlement_date),
                "confidence": self._calculate_confidence(transaction.amount, stl.amount)
            }
            for stl in settlements
        ]

    async def find_potential_transactions(self, settlement_id: str) -> list[dict]:
        """Find potential transaction matches for a settlement."""
        settlement = await self.get_settlement_by_id(settlement_id)
        if not settlement:
            return []

        # Find transactions within tolerance
        tolerance = settings.AMOUNT_TOLERANCE_PERCENT / Decimal("100")
        min_amount = settlement.amount * (1 - tolerance)
        max_amount = settlement.amount * (1 + tolerance)

        result = await self.db.execute(
            select(Transaction).where(
                and_(
                    Transaction.currency == settlement.currency,
                    Transaction.amount >= min_amount,
                    Transaction.amount <= max_amount,
                    Transaction.status == "captured"
                )
            ).limit(10)
        )
        transactions = result.scalars().all()

        return [
            {
                "id": txn.id,
                "transaction_id": txn.transaction_id,
                "amount": float(txn.amount),
                "currency": txn.currency,
                "timestamp": str(txn.timestamp),
                "confidence": self._calculate_confidence(settlement.amount, txn.amount)
            }
            for txn in transactions
        ]

    async def find_potential_transactions_for_adjustment(self, adjustment_id: str) -> list[dict]:
        """Find potential transaction matches for an adjustment."""
        adjustment = await self.get_adjustment_by_id(adjustment_id)
        if not adjustment:
            return []

        # Find transactions with matching amount (adjustments usually match exact amounts)
        tolerance = settings.AMOUNT_TOLERANCE_PERCENT / Decimal("100")
        min_amount = adjustment.amount * (1 - tolerance)
        max_amount = adjustment.amount * (1 + tolerance)

        result = await self.db.execute(
            select(Transaction).where(
                and_(
                    Transaction.currency == adjustment.currency,
                    Transaction.amount >= min_amount,
                    Transaction.amount <= max_amount
                )
            ).limit(10)
        )
        transactions = result.scalars().all()

        return [
            {
                "id": txn.id,
                "transaction_id": txn.transaction_id,
                "amount": float(txn.amount),
                "currency": txn.currency,
                "timestamp": str(txn.timestamp),
                "confidence": self._calculate_confidence(adjustment.amount, txn.amount)
            }
            for txn in transactions
        ]

    async def get_recent_matches(self, limit: int = 100) -> list[MatchResult]:
        """Get recent match results."""
        result = await self.db.execute(
            select(MatchResult)
            .order_by(MatchResult.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    def _calculate_confidence(self, amount1: Decimal, amount2: Decimal) -> int:
        """Calculate confidence score based on amount similarity."""
        if amount1 == 0 or amount2 == 0:
            return 0

        diff_pct = abs(float(amount1 - amount2)) / float(amount1) * 100

        if diff_pct == 0:
            return 100
        elif diff_pct <= 1:
            return 95
        elif diff_pct <= 3:
            return 85
        elif diff_pct <= 5:
            return 75
        else:
            return max(50, int(100 - diff_pct * 5))
