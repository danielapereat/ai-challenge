"""API endpoints for AI-powered analysis features."""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.services.ai_analysis import AIAnalysisService
from app.services.matching_service import MatchingService
from app.services.reporting import ReportingService
from app.schemas.analysis import (
    AIStatusResponse,
    MatchExplanationResponse,
    DiscrepancyAnalysisResponse,
    SuggestionRankingResponse,
    SummaryResponse,
    PatternDetectionResponse,
    AnomalyDetectionResponse
)

router = APIRouter()

# Initialize AI service (singleton)
ai_service = AIAnalysisService()


@router.get("/status", response_model=AIStatusResponse)
async def get_ai_status():
    """
    Check if AI analysis features are available.

    Returns the status of AI features and available capabilities.
    """
    return AIStatusResponse(
        ai_enabled=ai_service.is_available,
        model=ai_service.model if ai_service.is_available else None,
        features=[
            "match_explanation",
            "discrepancy_analysis",
            "suggestion_ranking",
            "executive_summary",
            "pattern_detection",
            "anomaly_detection"
        ] if ai_service.is_available else []
    )


@router.get("/explain-match/{match_id}", response_model=MatchExplanationResponse)
async def explain_match(
    match_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate AI-powered explanation for a specific match.

    Returns human-readable explanation of why records matched,
    what explains any differences, and a recommendation.
    """
    matching_service = MatchingService(db)

    # Get match and related records
    match_result = await matching_service.get_match_by_id(match_id)
    if not match_result:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")

    # Convert to dict for AI service
    match_dict = {
        "id": str(match_result.id),
        "match_id": str(match_result.id),
        "confidence_score": match_result.confidence_score,
        "match_reasons": match_result.match_reasons or [],
        "amount_difference": float(match_result.amount_difference) if match_result.amount_difference else 0,
        "date_difference_days": match_result.date_difference_days or 0
    }

    # Get transaction
    transaction = await matching_service.get_transaction_by_id(match_result.transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Related transaction not found")

    txn_dict = {
        "transaction_id": transaction.transaction_id,
        "amount": float(transaction.amount),
        "currency": transaction.currency,
        "timestamp": str(transaction.timestamp),
        "status": transaction.status,
        "merchant_order_id": transaction.merchant_order_id
    }

    # Get settlement or adjustment
    stl_dict = None
    adj_dict = None

    if match_result.settlement_id:
        settlement = await matching_service.get_settlement_by_id(match_result.settlement_id)
        if settlement:
            stl_dict = {
                "settlement_id": settlement.settlement_id,
                "settlement_reference": settlement.settlement_reference,
                "amount": float(settlement.amount),
                "currency": settlement.currency,
                "settlement_date": str(settlement.settlement_date),
                "transaction_reference": settlement.transaction_reference,
                "fees_deducted": float(settlement.fees_deducted) if settlement.fees_deducted else 0
            }

    if match_result.adjustment_id:
        adjustment = await matching_service.get_adjustment_by_id(match_result.adjustment_id)
        if adjustment:
            adj_dict = {
                "adjustment_id": adjustment.adjustment_id,
                "amount": float(adjustment.amount),
                "currency": adjustment.currency,
                "adjustment_type": adjustment.adjustment_type,
                "date": str(adjustment.date),
                "related_transaction_ref": adjustment.related_transaction_ref
            }

    result = await ai_service.explain_match(match_dict, txn_dict, stl_dict, adj_dict)
    return MatchExplanationResponse(**result)


@router.get("/analyze-discrepancy/{discrepancy_id}", response_model=DiscrepancyAnalysisResponse)
async def analyze_discrepancy(
    discrepancy_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze why a record is unmatched and identify root causes.

    Returns probable causes, likelihood estimates, and recommended actions.
    """
    reporting_service = ReportingService(db)

    # Get discrepancy
    discrepancy = await reporting_service.get_discrepancy_by_id(discrepancy_id)
    if not discrepancy:
        raise HTTPException(status_code=404, detail=f"Discrepancy {discrepancy_id} not found")

    disc_dict = {
        "discrepancy_id": str(discrepancy.id),
        "discrepancy_type": discrepancy.discrepancy_type,
        "severity": discrepancy.severity,
        "description": discrepancy.description,
        "amount": float(discrepancy.amount) if discrepancy.amount else 0,
        "currency": discrepancy.currency,
        "suggested_actions": discrepancy.suggested_actions or [],
        "suggested_matches": discrepancy.suggested_matches or []
    }

    # Get related records and suggestions
    related_records = await reporting_service.get_discrepancy_context(discrepancy_id)
    suggested_matches = discrepancy.suggested_matches or []

    result = await ai_service.analyze_discrepancy(disc_dict, related_records, suggested_matches)
    return DiscrepancyAnalysisResponse(**result)


@router.post("/rank-suggestions/{record_type}/{record_id}", response_model=SuggestionRankingResponse)
async def rank_suggestions(
    record_type: str,
    record_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Use AI to rank and explain potential matches for an unmatched record.

    Returns candidates ranked by AI confidence with detailed explanations.
    """
    if record_type not in ["transaction", "settlement", "adjustment"]:
        raise HTTPException(status_code=400, detail="Invalid record type. Must be: transaction, settlement, or adjustment")

    matching_service = MatchingService(db)

    # Get the unmatched record and its candidates
    if record_type == "transaction":
        record = await matching_service.get_transaction_by_id(record_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Transaction {record_id} not found")
        unmatched = {
            "type": "transaction",
            "id": record.transaction_id,
            "amount": float(record.amount),
            "currency": record.currency,
            "timestamp": str(record.timestamp)
        }
        candidates = await matching_service.find_potential_settlements(record_id)
    elif record_type == "settlement":
        record = await matching_service.get_settlement_by_id(record_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Settlement {record_id} not found")
        unmatched = {
            "type": "settlement",
            "id": record.settlement_id,
            "amount": float(record.amount),
            "currency": record.currency,
            "settlement_date": str(record.settlement_date)
        }
        candidates = await matching_service.find_potential_transactions(record_id)
    else:  # adjustment
        record = await matching_service.get_adjustment_by_id(record_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Adjustment {record_id} not found")
        unmatched = {
            "type": "adjustment",
            "id": record.adjustment_id,
            "amount": float(record.amount),
            "currency": record.currency,
            "adjustment_type": record.adjustment_type
        }
        candidates = await matching_service.find_potential_transactions_for_adjustment(record_id)

    # Convert candidates to dicts
    candidate_dicts = [
        {
            "candidate_id": c.get("id", c.get("transaction_id", c.get("settlement_id", ""))),
            "rule_based_confidence": c.get("confidence", 0),
            "amount": c.get("amount", 0),
            "currency": c.get("currency", ""),
            "date": str(c.get("date", c.get("timestamp", "")))
        }
        for c in (candidates or [])
    ]

    result = await ai_service.rank_suggestions(unmatched, candidate_dicts)
    return SuggestionRankingResponse(**result)


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    db: AsyncSession = Depends(get_db)
):
    """
    Generate executive summary of reconciliation results.

    Returns overall health assessment, key findings, concerns,
    and recommended actions for the finance team.
    """
    reporting_service = ReportingService(db)

    # Get reconciliation stats
    stats = await reporting_service.get_reconciliation_stats()

    # Get discrepancies for context
    discrepancies_result = await reporting_service.get_discrepancies(limit=20)
    discrepancies_list = discrepancies_result.get("discrepancies", [])
    discrepancies = [
        {
            "id": str(d.get("record", {}).get("id", "")),
            "type": d.get("type", ""),
            "severity": d.get("priority", "medium"),
            "amount": float(d.get("record", {}).get("amount", 0)),
            "currency": d.get("record", {}).get("currency", "")
        }
        for d in discrepancies_list
    ]

    # Get high priority items
    high_priority = await reporting_service.get_high_priority_discrepancies()
    high_priority_list = [
        {"id": str(d.id), "type": d.discrepancy_type, "severity": d.severity}
        for d in high_priority
    ]

    result = await ai_service.generate_summary(stats, discrepancies, high_priority_list)
    return SummaryResponse(**result)


@router.post("/detect-patterns", response_model=PatternDetectionResponse)
async def detect_patterns(
    time_range_days: int = Query(default=30, ge=1, le=365),
    min_occurrences: int = Query(default=3, ge=2, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Identify systemic patterns across discrepancies.

    Returns patterns that could be fixed with configuration changes,
    along with estimated financial impact.
    """
    reporting_service = ReportingService(db)

    # Get discrepancies for pattern analysis
    discrepancies_result = await reporting_service.get_discrepancies_for_period(days=time_range_days)
    discrepancies = [
        {
            "id": str(d.id),
            "type": d.discrepancy_type,
            "severity": d.severity,
            "amount": float(d.amount) if d.amount else 0,
            "currency": d.currency,
            "created_at": str(d.created_at) if hasattr(d, 'created_at') else "",
            "description": d.description
        }
        for d in discrepancies_result
    ]

    result = await ai_service.detect_patterns(discrepancies, time_range_days, min_occurrences)
    return PatternDetectionResponse(**result)


@router.get("/anomalies", response_model=AnomalyDetectionResponse)
async def detect_anomalies(
    db: AsyncSession = Depends(get_db)
):
    """
    Detect unusual patterns in reconciliation data.

    Identifies anomalies like unusual fees, settlement delays,
    or suspicious patterns that may require investigation.
    """
    reporting_service = ReportingService(db)
    matching_service = MatchingService(db)

    # Get recent data for anomaly detection
    matches = await matching_service.get_recent_matches(limit=200)
    matches_list = [
        {
            "id": str(m.id),
            "confidence_score": m.confidence_score,
            "amount_difference": float(m.amount_difference) if m.amount_difference else 0
        }
        for m in matches
    ]

    settlements = await reporting_service.get_recent_settlements(limit=200)
    settlements_list = [
        {
            "settlement_id": s.settlement_reference,
            "amount": float(s.amount),
            "fees_deducted": float(s.fees_deducted) if s.fees_deducted else 0,
            "gross_amount": float(s.gross_amount) if s.gross_amount else float(s.amount)
        }
        for s in settlements
    ]

    adjustments = await reporting_service.get_recent_adjustments(limit=200)
    adjustments_list = [
        {
            "adjustment_id": a.adjustment_id,
            "amount": float(a.amount),
            "adjustment_type": a.type
        }
        for a in adjustments
    ]

    result = await ai_service.detect_anomalies(matches_list, settlements_list, adjustments_list)
    return AnomalyDetectionResponse(**result)
