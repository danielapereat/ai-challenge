from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_

from app.models import Transaction, Settlement, Adjustment, MatchResult
from app.config import settings
from app.utils.currency import convert_to_usd
from app.utils.date_utils import days_between


class ReportingService:
    """Service for generating discrepancy reports and analytics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_discrepancies(
        self,
        discrepancy_type: Optional[str] = None,
        currency: Optional[str] = None,
        min_amount: Optional[Decimal] = None,
        priority: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Get discrepancies with filtering and suggested matches."""
        discrepancies = []

        # Get unmatched transactions
        if discrepancy_type is None or discrepancy_type == "unmatched_transactions":
            unmatched_txns = await self._get_unmatched_transactions(currency, min_amount)
            for txn in unmatched_txns:
                age_days = days_between(txn.timestamp, datetime.now())
                record_priority = self._calculate_priority(txn.amount, txn.currency, age_days)

                if priority and record_priority != priority:
                    continue

                discrepancies.append({
                    "type": "unmatched_transaction",
                    "record": {
                        "id": txn.id,
                        "transaction_id": txn.transaction_id,
                        "merchant_order_id": txn.merchant_order_id,
                        "amount": str(txn.amount),
                        "currency": txn.currency,
                        "timestamp": txn.timestamp.isoformat(),
                        "status": txn.status,
                        "country": txn.country,
                    },
                    "age_days": age_days,
                    "priority": record_priority,
                    "suggested_matches": await self._get_suggested_settlement_matches(txn),
                })

        # Get unmatched settlements
        if discrepancy_type is None or discrepancy_type == "unmatched_settlements":
            unmatched_stls = await self._get_unmatched_settlements(currency, min_amount)
            for stl in unmatched_stls:
                age_days = days_between(stl.settlement_date, date.today())
                record_priority = self._calculate_priority(stl.amount, stl.currency, age_days)

                if priority and record_priority != priority:
                    continue

                discrepancies.append({
                    "type": "unmatched_settlement",
                    "record": {
                        "id": stl.id,
                        "settlement_reference": stl.settlement_reference,
                        "amount": str(stl.amount),
                        "currency": stl.currency,
                        "settlement_date": stl.settlement_date.isoformat(),
                        "transaction_reference": stl.transaction_reference,
                        "bank_name": stl.bank_name,
                    },
                    "age_days": age_days,
                    "priority": record_priority,
                    "suggested_matches": await self._get_suggested_transaction_matches(stl),
                })

        # Get unmatched adjustments
        if discrepancy_type is None or discrepancy_type == "unmatched_adjustments":
            unmatched_adjs = await self._get_unmatched_adjustments(currency, min_amount)
            for adj in unmatched_adjs:
                age_days = days_between(adj.date, date.today())
                record_priority = self._calculate_priority(adj.amount, adj.currency, age_days, is_adjustment=True)

                if priority and record_priority != priority:
                    continue

                discrepancies.append({
                    "type": "unmatched_adjustment",
                    "record": {
                        "id": adj.id,
                        "adjustment_id": adj.adjustment_id,
                        "amount": str(adj.amount),
                        "currency": adj.currency,
                        "type": adj.type,
                        "date": adj.date.isoformat(),
                        "reason_code": adj.reason_code,
                        "transaction_reference": adj.transaction_reference,
                    },
                    "age_days": age_days,
                    "priority": record_priority,
                    "suggested_matches": [],
                })

        # Get amount mismatches
        if discrepancy_type is None or discrepancy_type == "amount_mismatches":
            mismatches = await self._get_amount_mismatches(currency, min_amount)
            for match in mismatches:
                transaction = match.transaction
                settlement = match.settlement

                discrepancies.append({
                    "type": "amount_mismatch",
                    "record": {
                        "match_id": match.id,
                        "transaction_id": transaction.transaction_id if transaction else None,
                        "settlement_reference": settlement.settlement_reference if settlement else None,
                        "transaction_amount": str(transaction.amount) if transaction else None,
                        "settlement_amount": str(settlement.amount) if settlement else None,
                        "difference": str(match.amount_difference),
                        "currency": transaction.currency if transaction else settlement.currency,
                    },
                    "age_days": match.date_difference_days,
                    "priority": "medium",
                    "suggested_matches": [],
                })

        # Calculate summary
        summary = await self._calculate_summary(discrepancies)

        # Apply pagination
        paginated = discrepancies[offset:offset + limit]

        return {
            "discrepancies": paginated,
            "summary": summary,
            "total": len(discrepancies),
        }

    async def get_summary(self) -> dict:
        """Get a high-level summary of discrepancies."""
        # Get unmatched values by currency
        unmatched_by_currency: dict[str, Decimal] = {}
        total_usd = Decimal("0")

        # Unmatched transactions
        unmatched_txns = await self._get_unmatched_transactions()
        for txn in unmatched_txns:
            currency = txn.currency
            unmatched_by_currency[currency] = unmatched_by_currency.get(currency, Decimal("0")) + txn.amount
            total_usd += convert_to_usd(txn.amount, currency)

        # Unmatched settlements
        unmatched_stls = await self._get_unmatched_settlements()
        for stl in unmatched_stls:
            currency = stl.currency
            unmatched_by_currency[currency] = unmatched_by_currency.get(currency, Decimal("0")) + stl.amount
            total_usd += convert_to_usd(stl.amount, currency)

        # Calculate average settlement time
        avg_settlement_hours = await self._calculate_avg_settlement_time()

        # Calculate chargeback rate
        chargeback_rate = await self._calculate_chargeback_rate()

        # Count orphaned records over 7 days
        orphaned_count = await self._count_orphaned_records()

        return {
            "total_unmatched_value_usd": float(total_usd),
            "unmatched_by_currency": {k: float(v) for k, v in unmatched_by_currency.items()},
            "avg_settlement_time_hours": avg_settlement_hours,
            "chargeback_rate": chargeback_rate,
            "orphaned_records_over_7_days": orphaned_count,
        }

    async def get_reconciliation_status(self) -> dict:
        """Get the status of the last reconciliation run."""
        # Get last match creation time
        stmt = select(MatchResult).order_by(MatchResult.created_at.desc()).limit(1)
        result = await self.db.execute(stmt)
        last_match = result.scalar_one_or_none()

        # Count total records
        txn_count = await self.db.scalar(select(func.count(Transaction.id)))
        stl_count = await self.db.scalar(select(func.count(Settlement.id)))
        adj_count = await self.db.scalar(select(func.count(Adjustment.id)))
        total_records = (txn_count or 0) + (stl_count or 0) + (adj_count or 0)

        # Count matches
        match_count = await self.db.scalar(select(func.count(MatchResult.id)))

        # Calculate match rate
        match_rate = (match_count or 0) / max(total_records, 1)

        return {
            "last_run": last_match.created_at.isoformat() if last_match else None,
            "total_records": total_records,
            "match_rate": round(match_rate, 4),
        }

    async def _get_unmatched_transactions(
        self,
        currency: Optional[str] = None,
        min_amount: Optional[Decimal] = None,
    ) -> list[Transaction]:
        """Get transactions that have not been matched to a settlement."""
        matched_ids_subquery = select(MatchResult.transaction_id).where(
            MatchResult.transaction_id.isnot(None),
            MatchResult.settlement_id.isnot(None)
        )

        stmt = select(Transaction).where(
            Transaction.status == "captured",
            Transaction.id.not_in(matched_ids_subquery)
        )

        if currency:
            stmt = stmt.where(Transaction.currency == currency.upper())
        if min_amount:
            stmt = stmt.where(Transaction.amount >= min_amount)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_unmatched_settlements(
        self,
        currency: Optional[str] = None,
        min_amount: Optional[Decimal] = None,
    ) -> list[Settlement]:
        """Get settlements that have not been matched to a transaction."""
        matched_ids_subquery = select(MatchResult.settlement_id).where(
            MatchResult.settlement_id.isnot(None)
        )

        stmt = select(Settlement).where(
            Settlement.id.not_in(matched_ids_subquery)
        )

        if currency:
            stmt = stmt.where(Settlement.currency == currency.upper())
        if min_amount:
            stmt = stmt.where(Settlement.amount >= min_amount)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_unmatched_adjustments(
        self,
        currency: Optional[str] = None,
        min_amount: Optional[Decimal] = None,
    ) -> list[Adjustment]:
        """Get adjustments that have not been matched to a transaction."""
        matched_ids_subquery = select(MatchResult.adjustment_id).where(
            MatchResult.adjustment_id.isnot(None)
        )

        stmt = select(Adjustment).where(
            Adjustment.id.not_in(matched_ids_subquery)
        )

        if currency:
            stmt = stmt.where(Adjustment.currency == currency.upper())
        if min_amount:
            stmt = stmt.where(Adjustment.amount >= min_amount)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_amount_mismatches(
        self,
        currency: Optional[str] = None,
        min_amount: Optional[Decimal] = None,
    ) -> list[MatchResult]:
        """Get matches that have amount discrepancies."""
        stmt = (
            select(MatchResult)
            .where(
                MatchResult.amount_difference > 0,
                MatchResult.settlement_id.isnot(None)
            )
            .options()
        )

        result = await self.db.execute(stmt)
        matches = list(result.scalars().all())

        # Load relationships and filter
        filtered = []
        for match in matches:
            if match.transaction_id:
                match.transaction = await self.db.get(Transaction, match.transaction_id)
            if match.settlement_id:
                match.settlement = await self.db.get(Settlement, match.settlement_id)

            if currency and match.transaction and match.transaction.currency != currency.upper():
                continue
            if min_amount and match.amount_difference < min_amount:
                continue

            filtered.append(match)

        return filtered

    def _calculate_priority(
        self,
        amount: Decimal,
        currency: str,
        age_days: int,
        is_adjustment: bool = False,
    ) -> str:
        """Calculate priority based on amount, age, and type."""
        usd_amount = convert_to_usd(amount, currency)

        # Chargebacks are always high priority
        if is_adjustment:
            return "high"

        # High priority: > $1000 USD or > 7 days old
        if usd_amount > Decimal("1000") or age_days > 7:
            return "high"

        # Medium priority: > $100 USD or > 3 days old
        if usd_amount > Decimal("100") or age_days > 3:
            return "medium"

        return "low"

    async def _get_suggested_settlement_matches(
        self, transaction: Transaction, limit: int = 3
    ) -> list[dict]:
        """Get suggested settlement matches for a transaction."""
        suggestions = []

        # Find unmatched settlements
        matched_ids_subquery = select(MatchResult.settlement_id).where(
            MatchResult.settlement_id.isnot(None)
        )

        stmt = select(Settlement).where(
            Settlement.id.not_in(matched_ids_subquery)
        )

        result = await self.db.execute(stmt)
        settlements = result.scalars().all()

        for settlement in settlements:
            confidence, reasons = self._score_match(transaction, settlement)
            if confidence > 30:
                suggestions.append({
                    "record_type": "settlement",
                    "record": {
                        "id": settlement.id,
                        "settlement_reference": settlement.settlement_reference,
                        "amount": str(settlement.amount),
                        "currency": settlement.currency,
                    },
                    "confidence": confidence,
                    "reasons": reasons,
                })

        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        return suggestions[:limit]

    async def _get_suggested_transaction_matches(
        self, settlement: Settlement, limit: int = 3
    ) -> list[dict]:
        """Get suggested transaction matches for a settlement."""
        suggestions = []

        # Find unmatched transactions
        matched_ids_subquery = select(MatchResult.transaction_id).where(
            MatchResult.transaction_id.isnot(None),
            MatchResult.settlement_id.isnot(None)
        )

        stmt = select(Transaction).where(
            Transaction.status == "captured",
            Transaction.id.not_in(matched_ids_subquery)
        )

        result = await self.db.execute(stmt)
        transactions = result.scalars().all()

        for transaction in transactions:
            confidence, reasons = self._score_match(transaction, settlement)
            if confidence > 30:
                suggestions.append({
                    "record_type": "transaction",
                    "record": {
                        "id": transaction.id,
                        "transaction_id": transaction.transaction_id,
                        "amount": str(transaction.amount),
                        "currency": transaction.currency,
                    },
                    "confidence": confidence,
                    "reasons": reasons,
                })

        suggestions.sort(key=lambda x: x["confidence"], reverse=True)
        return suggestions[:limit]

    def _score_match(self, transaction: Transaction, settlement: Settlement) -> tuple[int, list[str]]:
        """Score a potential match between transaction and settlement."""
        confidence = 0
        reasons = []

        # Currency match
        if settlement.currency == transaction.currency:
            confidence += 20
            reasons.append("currency_match")

        # Amount tolerance
        tolerance = settings.AMOUNT_TOLERANCE_PERCENT / Decimal("100")
        if transaction.amount > 0:
            diff_percent = abs(settlement.amount - transaction.amount) / transaction.amount
            if diff_percent == 0:
                confidence += 40
                reasons.append("exact_amount")
            elif diff_percent <= tolerance:
                confidence += 25
                reasons.append("amount_within_tolerance")

        # Date proximity
        day_diff = days_between(settlement.settlement_date, transaction.timestamp)
        if day_diff <= 3:
            confidence += 20
            reasons.append("date_within_72h")
        elif day_diff <= 7:
            confidence += 10
            reasons.append("date_within_7d")

        # Reference match
        if settlement.transaction_reference:
            if settlement.transaction_reference == transaction.transaction_id:
                confidence += 20
                reasons.append("id_match")

        return min(confidence, 100), reasons

    async def _calculate_summary(self, discrepancies: list[dict]) -> dict:
        """Calculate summary statistics for discrepancies."""
        by_type = {
            "unmatched_transactions": 0,
            "unmatched_settlements": 0,
            "unmatched_adjustments": 0,
            "amount_mismatches": 0,
        }

        total_unmatched_value: dict[str, Decimal] = {}

        for d in discrepancies:
            dtype = d["type"]
            if dtype in by_type:
                by_type[dtype] += 1

            record = d.get("record", {})
            amount_str = record.get("amount")
            currency = record.get("currency")

            if amount_str and currency:
                amount = Decimal(amount_str)
                total_unmatched_value[currency] = total_unmatched_value.get(currency, Decimal("0")) + amount

        return {
            "total_unmatched_value": {k: float(v) for k, v in total_unmatched_value.items()},
            "by_type": by_type,
        }

    async def _calculate_avg_settlement_time(self) -> Optional[float]:
        """Calculate average settlement time in hours."""
        stmt = select(MatchResult).where(
            MatchResult.match_type == "transaction_settlement",
            MatchResult.status == "matched"
        )
        result = await self.db.execute(stmt)
        matches = result.scalars().all()

        if not matches:
            return None

        total_hours = sum(m.date_difference_days * 24 for m in matches)
        return round(total_hours / len(matches), 2)

    async def _calculate_chargeback_rate(self) -> float:
        """Calculate chargeback rate as a percentage of total transactions."""
        total_txns = await self.db.scalar(select(func.count(Transaction.id)))
        total_chargebacks = await self.db.scalar(
            select(func.count(Adjustment.id)).where(Adjustment.type == "chargeback")
        )

        if not total_txns:
            return 0.0

        return round((total_chargebacks or 0) / total_txns, 4)

    async def _count_orphaned_records(self) -> int:
        """Count records that have been unmatched for more than 7 days."""
        threshold_date = date.today() - timedelta(days=settings.ORPHAN_THRESHOLD_DAYS)
        count = 0

        # Unmatched transactions
        unmatched_txns = await self._get_unmatched_transactions()
        for txn in unmatched_txns:
            if txn.timestamp.date() < threshold_date:
                count += 1

        # Unmatched settlements
        unmatched_stls = await self._get_unmatched_settlements()
        for stl in unmatched_stls:
            if stl.settlement_date < threshold_date:
                count += 1

        # Unmatched adjustments
        unmatched_adjs = await self._get_unmatched_adjustments()
        for adj in unmatched_adjs:
            if adj.date < threshold_date:
                count += 1

        return count
