from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import MatchResult, Transaction, Settlement, Adjustment
from app.schemas.discrepancy import MatchResponse, MatchListResponse

router = APIRouter()


@router.get("", response_model=MatchListResponse)
async def get_matches(
    confidence_min: int = Query(0, ge=0, le=100, description="Minimum confidence score"),
    status: Optional[str] = Query(None, description="Filter by status: matched, pending_review, unmatched"),
    match_type: Optional[str] = Query(None, description="Filter by type: transaction_settlement, transaction_adjustment"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Get match results with filtering."""
    stmt = select(MatchResult).options(
        selectinload(MatchResult.transaction),
        selectinload(MatchResult.settlement),
        selectinload(MatchResult.adjustment)
    ).where(MatchResult.confidence_score >= confidence_min)

    if status:
        stmt = stmt.where(MatchResult.status == status)
    if match_type:
        stmt = stmt.where(MatchResult.match_type == match_type)

    stmt = stmt.order_by(MatchResult.confidence_score.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    matches = result.scalars().all()

    # Build response with related records
    match_responses = []
    for match in matches:
        transaction_data = None
        settlement_data = None
        adjustment_data = None

        if match.transaction:
            transaction = match.transaction
            transaction_data = {
                "id": transaction.id,
                "transaction_id": transaction.transaction_id,
                "merchant_order_id": transaction.merchant_order_id,
                "amount": str(transaction.amount),
                "currency": transaction.currency,
                "timestamp": transaction.timestamp.isoformat(),
                "status": transaction.status,
                "country": transaction.country,
            }

        if match.settlement:
            settlement = match.settlement
            settlement_data = {
                "id": settlement.id,
                "settlement_reference": settlement.settlement_reference,
                "amount": str(settlement.amount),
                "currency": settlement.currency,
                "settlement_date": settlement.settlement_date.isoformat(),
                "bank_name": settlement.bank_name,
            }

        if match.adjustment:
            adjustment = match.adjustment
            adjustment_data = {
                "id": adjustment.id,
                "adjustment_id": adjustment.adjustment_id,
                "amount": str(adjustment.amount),
                "currency": adjustment.currency,
                "type": adjustment.type,
                "date": adjustment.date.isoformat(),
            }

        match_responses.append(MatchResponse(
            id=match.id,
            transaction=transaction_data,
            settlement=settlement_data,
            adjustment=adjustment_data,
            confidence=match.confidence_score,
            match_reasons=match.match_reasons,
            amount_difference=match.amount_difference,
            date_difference_days=match.date_difference_days,
            status=match.status,
        ))

    # Get total count
    count_stmt = select(func.count(MatchResult.id)).where(MatchResult.confidence_score >= confidence_min)
    if status:
        count_stmt = count_stmt.where(MatchResult.status == status)
    if match_type:
        count_stmt = count_stmt.where(MatchResult.match_type == match_type)
    total = await db.scalar(count_stmt) or 0

    return MatchListResponse(matches=match_responses, total=total)


@router.get("/{transaction_id}", response_model=MatchResponse)
async def get_match_by_transaction(
    transaction_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get match result for a specific transaction ID."""
    # First find the transaction
    stmt = select(Transaction).where(Transaction.transaction_id == transaction_id)
    result = await db.execute(stmt)
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")

    # Find the match
    stmt = select(MatchResult).where(MatchResult.transaction_id == transaction.id)
    result = await db.execute(stmt)
    match = result.scalar_one_or_none()

    if not match:
        raise HTTPException(
            status_code=404,
            detail=f"No match found for transaction {transaction_id}"
        )

    # Build response
    transaction_data = {
        "id": transaction.id,
        "transaction_id": transaction.transaction_id,
        "merchant_order_id": transaction.merchant_order_id,
        "amount": str(transaction.amount),
        "currency": transaction.currency,
        "timestamp": transaction.timestamp.isoformat(),
        "status": transaction.status,
        "country": transaction.country,
    }

    settlement_data = None
    adjustment_data = None

    if match.settlement_id:
        settlement = await db.get(Settlement, match.settlement_id)
        if settlement:
            settlement_data = {
                "id": settlement.id,
                "settlement_reference": settlement.settlement_reference,
                "amount": str(settlement.amount),
                "currency": settlement.currency,
                "settlement_date": settlement.settlement_date.isoformat(),
                "bank_name": settlement.bank_name,
            }

    if match.adjustment_id:
        adjustment = await db.get(Adjustment, match.adjustment_id)
        if adjustment:
            adjustment_data = {
                "id": adjustment.id,
                "adjustment_id": adjustment.adjustment_id,
                "amount": str(adjustment.amount),
                "currency": adjustment.currency,
                "type": adjustment.type,
                "date": adjustment.date.isoformat(),
            }

    return MatchResponse(
        id=match.id,
        transaction=transaction_data,
        settlement=settlement_data,
        adjustment=adjustment_data,
        confidence=match.confidence_score,
        match_reasons=match.match_reasons,
        amount_difference=match.amount_difference,
        date_difference_days=match.date_difference_days,
        status=match.status,
    )
