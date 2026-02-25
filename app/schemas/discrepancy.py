from datetime import datetime, date
from decimal import Decimal
from typing import Optional, Any
from pydantic import BaseModel, Field


class SuggestedMatch(BaseModel):
    record_type: str  # settlement | adjustment
    record: dict
    confidence: int
    reasons: list[str]


class DiscrepancyRecord(BaseModel):
    type: str  # unmatched_transaction | unmatched_settlement | unmatched_adjustment | amount_mismatch
    record: dict
    age_days: int
    priority: str  # high | medium | low
    suggested_matches: list[SuggestedMatch] = []


class DiscrepancySummaryByType(BaseModel):
    unmatched_transactions: int = 0
    unmatched_settlements: int = 0
    unmatched_adjustments: int = 0
    amount_mismatches: int = 0


class DiscrepancyResponse(BaseModel):
    discrepancies: list[DiscrepancyRecord]
    summary: dict


class DiscrepancySummary(BaseModel):
    total_unmatched_value_usd: Decimal
    unmatched_by_currency: dict[str, Decimal]
    avg_settlement_time_hours: Optional[float]
    chargeback_rate: float
    orphaned_records_over_7_days: int


class ReconcileRequest(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class ReconcileResponse(BaseModel):
    matched: int
    unmatched_transactions: int
    unmatched_settlements: int
    unmatched_adjustments: int
    amount_mismatches: int
    processing_time_ms: int


class ReconcileStatus(BaseModel):
    last_run: Optional[datetime]
    total_records: int
    match_rate: float


class MatchResponse(BaseModel):
    id: str
    transaction: Optional[dict]
    settlement: Optional[dict]
    adjustment: Optional[dict]
    confidence: int
    match_reasons: list[str]
    amount_difference: Decimal
    date_difference_days: int
    status: str

    class Config:
        from_attributes = True


class MatchListResponse(BaseModel):
    matches: list[MatchResponse]
    total: int
