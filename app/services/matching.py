from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete

from app.models import Transaction, Settlement, Adjustment, MatchResult
from app.config import settings
from app.utils.currency import convert_to_usd, convert_currency
from app.utils.date_utils import days_between, hours_between


class MatchingEngine:
    """Core matching engine for reconciling transactions, settlements, and adjustments."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.matched_transaction_ids: set[str] = set()
        self.matched_settlement_ids: set[str] = set()
        self.matched_adjustment_ids: set[str] = set()

    async def run_reconciliation(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> dict:
        """Run the full reconciliation process."""
        start_time = datetime.now()

        # Clear previous match results
        await self._clear_previous_matches()

        # Load data
        transactions = await self._load_transactions(date_from, date_to)
        settlements = await self._load_settlements(date_from, date_to)
        adjustments = await self._load_adjustments(date_from, date_to)

        matches = []
        amount_mismatches = 0

        # Phase 1: Exact transaction ID matches
        phase1_matches = await self._phase1_exact_id_match(transactions, settlements)
        matches.extend(phase1_matches)

        # Phase 2: Amount + date window matches
        phase2_matches, phase2_mismatches = await self._phase2_amount_date_match(
            transactions, settlements
        )
        matches.extend(phase2_matches)
        amount_mismatches += phase2_mismatches

        # Phase 3: Fuzzy matches (partial ID, merchant order ID)
        phase3_matches = await self._phase3_fuzzy_match(transactions, settlements)
        matches.extend(phase3_matches)

        # Phase 4: Cross-currency matches
        phase4_matches = await self._phase4_cross_currency_match(transactions, settlements)
        matches.extend(phase4_matches)

        # Phase 5: Adjustment matching
        phase5_matches = await self._phase5_adjustment_match(transactions, adjustments)
        matches.extend(phase5_matches)

        # Save all matches
        for match in matches:
            self.db.add(match)
        await self.db.commit()

        # Calculate stats
        unmatched_transactions = len(transactions) - len(self.matched_transaction_ids)
        unmatched_settlements = len(settlements) - len(self.matched_settlement_ids)
        unmatched_adjustments = len(adjustments) - len(self.matched_adjustment_ids)

        processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        return {
            "matched": len(matches),
            "unmatched_transactions": unmatched_transactions,
            "unmatched_settlements": unmatched_settlements,
            "unmatched_adjustments": unmatched_adjustments,
            "amount_mismatches": amount_mismatches,
            "processing_time_ms": processing_time_ms,
        }

    async def _clear_previous_matches(self):
        """Clear all previous match results."""
        stmt = delete(MatchResult)
        await self.db.execute(stmt)
        await self.db.commit()

    async def _load_transactions(
        self, date_from: Optional[date], date_to: Optional[date]
    ) -> list[Transaction]:
        """Load transactions within the date range."""
        stmt = select(Transaction).where(Transaction.status == "captured")

        if date_from:
            stmt = stmt.where(Transaction.timestamp >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            stmt = stmt.where(Transaction.timestamp <= datetime.combine(date_to, datetime.max.time()))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _load_settlements(
        self, date_from: Optional[date], date_to: Optional[date]
    ) -> list[Settlement]:
        """Load settlements within the date range."""
        stmt = select(Settlement)

        if date_from:
            stmt = stmt.where(Settlement.settlement_date >= date_from)
        if date_to:
            stmt = stmt.where(Settlement.settlement_date <= date_to)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _load_adjustments(
        self, date_from: Optional[date], date_to: Optional[date]
    ) -> list[Adjustment]:
        """Load adjustments within the date range."""
        stmt = select(Adjustment)

        if date_from:
            stmt = stmt.where(Adjustment.date >= date_from)
        if date_to:
            stmt = stmt.where(Adjustment.date <= date_to)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _phase1_exact_id_match(
        self, transactions: list[Transaction], settlements: list[Settlement]
    ) -> list[MatchResult]:
        """Phase 1: Match by exact transaction ID."""
        matches = []

        for settlement in settlements:
            if settlement.id in self.matched_settlement_ids:
                continue
            if not settlement.transaction_reference:
                continue

            for transaction in transactions:
                if transaction.id in self.matched_transaction_ids:
                    continue

                if (
                    settlement.transaction_reference == transaction.transaction_id
                    and settlement.currency == transaction.currency
                ):
                    amount_diff = abs(settlement.amount - transaction.amount)
                    date_diff = days_between(settlement.settlement_date, transaction.timestamp)

                    match = MatchResult(
                        transaction_id=transaction.id,
                        settlement_id=settlement.id,
                        match_type="transaction_settlement",
                        confidence_score=100,
                        match_reasons=["exact_transaction_id_match", "currency_match"],
                        amount_difference=amount_diff,
                        date_difference_days=date_diff,
                        status="matched",
                    )
                    matches.append(match)
                    self.matched_transaction_ids.add(transaction.id)
                    self.matched_settlement_ids.add(settlement.id)
                    break

        return matches

    async def _phase2_amount_date_match(
        self, transactions: list[Transaction], settlements: list[Settlement]
    ) -> tuple[list[MatchResult], int]:
        """Phase 2: Match by amount and date window."""
        matches = []
        amount_mismatches = 0
        tolerance = settings.AMOUNT_TOLERANCE_PERCENT / Decimal("100")
        window_hours = settings.SETTLEMENT_WINDOW_HOURS

        for settlement in settlements:
            if settlement.id in self.matched_settlement_ids:
                continue

            best_match = None
            best_confidence = 0

            for transaction in transactions:
                if transaction.id in self.matched_transaction_ids:
                    continue
                if settlement.currency != transaction.currency:
                    continue

                # Check amount tolerance
                amount_diff = abs(settlement.amount - transaction.amount)
                if transaction.amount == 0 and settlement.amount == 0:
                    amount_diff_percent = Decimal("0")  # Perfect match for zero amounts
                elif transaction.amount > 0:
                    amount_diff_percent = amount_diff / transaction.amount
                else:
                    continue  # Skip if transaction is 0 but settlement isn't

                if amount_diff_percent > tolerance:
                    continue

                # Check date window
                settlement_dt = datetime.combine(settlement.settlement_date, datetime.min.time())
                if transaction.timestamp.tzinfo:
                    settlement_dt = settlement_dt.replace(tzinfo=transaction.timestamp.tzinfo)

                hours_diff = hours_between(settlement_dt, transaction.timestamp)
                if hours_diff > window_hours:
                    continue

                # Calculate confidence score
                confidence = 80

                # Amount bonuses
                if amount_diff == 0:
                    confidence += 15
                elif amount_diff_percent <= Decimal("0.01"):
                    confidence += 10
                elif amount_diff_percent <= Decimal("0.05"):
                    confidence += 5

                # Date bonuses
                day_diff = days_between(settlement.settlement_date, transaction.timestamp)
                if day_diff == 0:
                    confidence += 5
                elif day_diff <= 1:
                    confidence += 3
                elif day_diff <= 2:
                    confidence += 1

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = (transaction, amount_diff, day_diff)

            if best_match and best_confidence >= settings.MIN_CONFIDENCE_FOR_AUTO_MATCH:
                transaction, amount_diff, day_diff = best_match

                reasons = ["amount_within_tolerance", "date_within_window"]
                if amount_diff > 0:
                    reasons.append("amount_variance_detected")
                    amount_mismatches += 1

                status = "matched" if best_confidence >= 80 else "pending_review"

                match = MatchResult(
                    transaction_id=transaction.id,
                    settlement_id=settlement.id,
                    match_type="transaction_settlement",
                    confidence_score=best_confidence,
                    match_reasons=reasons,
                    amount_difference=amount_diff,
                    date_difference_days=day_diff,
                    status=status,
                )
                matches.append(match)
                self.matched_transaction_ids.add(transaction.id)
                self.matched_settlement_ids.add(settlement.id)

        return matches, amount_mismatches

    async def _phase3_fuzzy_match(
        self, transactions: list[Transaction], settlements: list[Settlement]
    ) -> list[MatchResult]:
        """Phase 3: Fuzzy matching (partial ID, merchant order ID)."""
        matches = []
        tolerance = settings.AMOUNT_TOLERANCE_PERCENT / Decimal("100")

        for settlement in settlements:
            if settlement.id in self.matched_settlement_ids:
                continue
            if not settlement.transaction_reference:
                continue

            best_match = None
            best_confidence = 0

            for transaction in transactions:
                if transaction.id in self.matched_transaction_ids:
                    continue
                if settlement.currency != transaction.currency:
                    continue

                confidence = 0
                reasons = []

                # Check partial ID match (first 8 chars)
                if len(settlement.transaction_reference) >= 8 and len(transaction.transaction_id) >= 8:
                    if (
                        settlement.transaction_reference[:8] in transaction.transaction_id
                        or transaction.transaction_id[:8] in settlement.transaction_reference
                    ):
                        confidence = 70
                        reasons.append("partial_id_match")

                # Check merchant order ID match
                if settlement.transaction_reference == transaction.merchant_order_id:
                    confidence = max(confidence, 75)
                    if "partial_id_match" not in reasons:
                        reasons = ["merchant_order_id_match"]
                    else:
                        reasons.append("merchant_order_id_match")

                if confidence == 0:
                    continue

                # Verify amount tolerance
                amount_diff = abs(settlement.amount - transaction.amount)
                if transaction.amount == 0 and settlement.amount == 0:
                    amount_diff_percent = Decimal("0")  # Perfect match for zero amounts
                elif transaction.amount > 0:
                    amount_diff_percent = amount_diff / transaction.amount
                else:
                    continue  # Skip if transaction is 0 but settlement isn't

                if amount_diff_percent > tolerance:
                    continue

                # Adjust confidence based on amount match
                if amount_diff == 0:
                    confidence += 15
                elif amount_diff_percent <= Decimal("0.02"):
                    confidence += 10
                reasons.append("amount_within_tolerance")

                if confidence > best_confidence:
                    best_confidence = confidence
                    day_diff = days_between(settlement.settlement_date, transaction.timestamp)
                    best_match = (transaction, amount_diff, day_diff, reasons)

            if best_match:
                transaction, amount_diff, day_diff, reasons = best_match

                match = MatchResult(
                    transaction_id=transaction.id,
                    settlement_id=settlement.id,
                    match_type="transaction_settlement",
                    confidence_score=best_confidence,
                    match_reasons=reasons,
                    amount_difference=amount_diff,
                    date_difference_days=day_diff,
                    status="matched" if best_confidence >= 80 else "pending_review",
                )
                matches.append(match)
                self.matched_transaction_ids.add(transaction.id)
                self.matched_settlement_ids.add(settlement.id)

        return matches

    async def _phase4_cross_currency_match(
        self, transactions: list[Transaction], settlements: list[Settlement]
    ) -> list[MatchResult]:
        """Phase 4: Cross-currency matching."""
        matches = []
        fx_tolerance = settings.CURRENCY_FX_TOLERANCE_PERCENT / Decimal("100")
        window_hours = settings.SETTLEMENT_WINDOW_HOURS

        for settlement in settlements:
            if settlement.id in self.matched_settlement_ids:
                continue

            best_match = None
            best_confidence = 0

            for transaction in transactions:
                if transaction.id in self.matched_transaction_ids:
                    continue
                if settlement.currency == transaction.currency:
                    continue  # Already handled in earlier phases

                # Convert settlement amount to transaction currency
                converted_amount = convert_currency(
                    settlement.amount, settlement.currency, transaction.currency
                )

                amount_diff = abs(converted_amount - transaction.amount)
                if transaction.amount == 0 and converted_amount == 0:
                    amount_diff_percent = Decimal("0")  # Perfect match for zero amounts
                elif transaction.amount > 0:
                    amount_diff_percent = amount_diff / transaction.amount
                else:
                    continue  # Skip if transaction is 0 but settlement isn't

                if amount_diff_percent > fx_tolerance:
                    continue

                # Check date window
                settlement_dt = datetime.combine(settlement.settlement_date, datetime.min.time())
                if transaction.timestamp.tzinfo:
                    settlement_dt = settlement_dt.replace(tzinfo=transaction.timestamp.tzinfo)

                hours_diff = hours_between(settlement_dt, transaction.timestamp)
                if hours_diff > window_hours:
                    continue

                confidence = 60

                # Adjust based on amount match
                if amount_diff_percent <= Decimal("0.05"):
                    confidence += 15
                elif amount_diff_percent <= Decimal("0.08"):
                    confidence += 10

                # Check for ID match
                if settlement.transaction_reference:
                    if settlement.transaction_reference == transaction.transaction_id:
                        confidence += 20

                if confidence > best_confidence:
                    best_confidence = confidence
                    day_diff = days_between(settlement.settlement_date, transaction.timestamp)
                    best_match = (transaction, amount_diff, day_diff)

            if best_match and best_confidence >= 60:
                transaction, amount_diff, day_diff = best_match

                match = MatchResult(
                    transaction_id=transaction.id,
                    settlement_id=settlement.id,
                    match_type="transaction_settlement",
                    confidence_score=best_confidence,
                    match_reasons=["cross_currency_match", "amount_within_fx_tolerance", "needs_review"],
                    amount_difference=amount_diff,
                    date_difference_days=day_diff,
                    status="pending_review",
                )
                matches.append(match)
                self.matched_transaction_ids.add(transaction.id)
                self.matched_settlement_ids.add(settlement.id)

        return matches

    async def _phase5_adjustment_match(
        self, transactions: list[Transaction], adjustments: list[Adjustment]
    ) -> list[MatchResult]:
        """Phase 5: Match adjustments to transactions."""
        matches = []

        for adjustment in adjustments:
            if adjustment.id in self.matched_adjustment_ids:
                continue

            # Determine window based on adjustment type
            if adjustment.type == "chargeback":
                window_days = settings.CHARGEBACK_WINDOW_DAYS
            else:
                window_days = settings.REFUND_WINDOW_DAYS

            best_match = None
            best_confidence = 0

            for transaction in transactions:
                confidence = 0
                reasons = []

                # Check exact transaction reference match
                if adjustment.transaction_reference:
                    if adjustment.transaction_reference == transaction.transaction_id:
                        confidence = 100
                        reasons.append("exact_transaction_id_match")
                    elif adjustment.transaction_reference == transaction.merchant_order_id:
                        confidence = 90
                        reasons.append("merchant_order_id_match")

                if confidence == 0:
                    continue

                # Verify currency match
                if adjustment.currency != transaction.currency:
                    confidence -= 20
                    reasons.append("currency_mismatch")

                # Verify amount (adjustment should be <= transaction amount)
                if adjustment.amount > transaction.amount:
                    confidence -= 10
                    reasons.append("adjustment_exceeds_transaction")

                # Check date window
                day_diff = days_between(adjustment.date, transaction.timestamp)
                if day_diff > window_days:
                    continue

                reasons.append("date_within_window")

                if confidence > best_confidence:
                    best_confidence = confidence
                    amount_diff = abs(adjustment.amount - transaction.amount)
                    best_match = (transaction, amount_diff, day_diff, reasons)

            if best_match:
                transaction, amount_diff, day_diff, reasons = best_match

                match = MatchResult(
                    transaction_id=transaction.id,
                    adjustment_id=adjustment.id,
                    match_type="transaction_adjustment",
                    confidence_score=best_confidence,
                    match_reasons=reasons,
                    amount_difference=amount_diff,
                    date_difference_days=day_diff,
                    status="matched" if best_confidence >= 80 else "pending_review",
                )
                matches.append(match)
                self.matched_adjustment_ids.add(adjustment.id)

        return matches

    async def get_suggested_matches(
        self, record_type: str, record_id: str, limit: int = 5
    ) -> list[dict]:
        """Get suggested matches for an unmatched record."""
        suggestions = []

        if record_type == "transaction":
            transaction = await self.db.get(Transaction, record_id)
            if not transaction:
                return suggestions

            # Find potential settlement matches
            stmt = select(Settlement).where(
                Settlement.id.not_in(
                    select(MatchResult.settlement_id).where(MatchResult.settlement_id.isnot(None))
                )
            )
            result = await self.db.execute(stmt)
            settlements = result.scalars().all()

            for settlement in settlements:
                confidence, reasons = self._calculate_match_score(transaction, settlement)
                if confidence > 30:
                    suggestions.append({
                        "record_type": "settlement",
                        "record": {
                            "id": settlement.id,
                            "settlement_reference": settlement.settlement_reference,
                            "amount": str(settlement.amount),
                            "currency": settlement.currency,
                            "settlement_date": str(settlement.settlement_date),
                        },
                        "confidence": confidence,
                        "reasons": reasons,
                    })

            suggestions.sort(key=lambda x: x["confidence"], reverse=True)

        return suggestions[:limit]

    def _calculate_match_score(
        self, transaction: Transaction, settlement: Settlement
    ) -> tuple[int, list[str]]:
        """Calculate a match score between a transaction and settlement."""
        confidence = 0
        reasons = []

        # Currency match
        if settlement.currency == transaction.currency:
            confidence += 20
            reasons.append("currency_match")

        # Amount comparison
        tolerance = settings.AMOUNT_TOLERANCE_PERCENT / Decimal("100")
        if transaction.amount == 0 and settlement.amount == 0:
            amount_diff_percent = Decimal("0")  # Perfect match for zero amounts
        elif transaction.amount > 0:
            amount_diff_percent = abs(settlement.amount - transaction.amount) / transaction.amount
        else:
            amount_diff_percent = Decimal("1")  # Treat as no match

        if amount_diff_percent == 0:
            confidence += 40
            reasons.append("exact_amount_match")
        elif amount_diff_percent <= tolerance:
            confidence += 30
            reasons.append("amount_within_tolerance")

        # Date proximity
        day_diff = days_between(settlement.settlement_date, transaction.timestamp)
        if day_diff <= 3:
            confidence += 20
            reasons.append("date_within_72h")
        elif day_diff <= 7:
            confidence += 10
            reasons.append("date_within_7d")

        # Reference matching
        if settlement.transaction_reference:
            if settlement.transaction_reference == transaction.transaction_id:
                confidence += 20
                reasons.append("transaction_id_match")
            elif settlement.transaction_reference == transaction.merchant_order_id:
                confidence += 15
                reasons.append("merchant_order_id_match")

        return min(confidence, 100), reasons
