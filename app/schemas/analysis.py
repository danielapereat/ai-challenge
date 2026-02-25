"""Pydantic schemas for AI analysis responses."""
from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from datetime import datetime


class ConfidenceBreakdownItem(BaseModel):
    contribution: int = Field(..., ge=0, le=100, description="Points contributed to confidence score")
    detail: str


class MatchExplanationResponse(BaseModel):
    match_id: str
    confidence: int = Field(..., ge=0, le=100, description="Overall confidence score 0-100")
    explanation: str
    confidence_breakdown: dict[str, ConfidenceBreakdownItem]
    warnings: list[str]
    recommendation: Literal["approve", "review", "reject"]
    ai_generated: bool


class RootCauseProbability(BaseModel):
    cause: str
    probability: float = Field(..., ge=0.0, le=1.0, description="Probability 0-1")
    evidence: list[str]


class SuggestedAction(BaseModel):
    action: str
    confidence: Literal["high", "medium", "low"]
    reasoning: str


class SimilarCase(BaseModel):
    discrepancy_id: str
    resolution: str
    resolved_in_hours: int = Field(..., ge=0)


class PotentialMatch(BaseModel):
    transaction_id: Optional[str] = None
    settlement_id: Optional[str] = None
    current_confidence: int = Field(..., ge=0, le=100)
    missing_factors: list[str]
    ai_confidence: int = Field(..., ge=0, le=100)
    ai_reasoning: str


class DiscrepancyAnalysisDetail(BaseModel):
    summary: str
    root_cause_probabilities: list[RootCauseProbability]
    investigation_priority: Literal["high", "medium", "low"]
    priority_reasoning: str


class DiscrepancyAnalysisResponse(BaseModel):
    discrepancy_id: str
    discrepancy_type: str
    analysis: DiscrepancyAnalysisDetail
    suggested_actions: list[SuggestedAction]
    similar_resolved_cases: list[SimilarCase]
    potential_matches: list[PotentialMatch]
    ai_generated: bool


class RankedSuggestion(BaseModel):
    candidate_id: str
    rule_based_confidence: int = Field(..., ge=0, le=100)
    ai_confidence: int = Field(..., ge=0, le=100)
    reasoning: str
    recommended_action: str


class SuggestionRankingResponse(BaseModel):
    unmatched_record: dict[str, Any]
    ai_ranked_suggestions: list[RankedSuggestion]
    ai_generated: bool


class KeyMetrics(BaseModel):
    total_transactions: int = Field(..., ge=0)
    matched: int = Field(..., ge=0)
    unmatched_transactions: int = Field(..., ge=0)
    unmatched_settlements: int = Field(..., ge=0)
    unmatched_adjustments: int = Field(..., ge=0)
    total_discrepancy_value_usd: float = Field(..., ge=0)


class SummaryResponse(BaseModel):
    summary: str
    health_status: Literal["good", "concerning", "critical"]
    match_rate: float = Field(..., ge=0.0, le=1.0, description="Match rate as decimal 0-1")
    key_metrics: KeyMetrics
    high_priority_items: int = Field(..., ge=0)
    generated_at: datetime
    ai_generated: bool


class ConfigChange(BaseModel):
    setting: str
    scope: str
    current_value: str
    recommended_value: str


class DetectedPattern(BaseModel):
    pattern_id: str
    pattern_type: str
    description: str
    affected_discrepancies: int = Field(..., ge=0)
    financial_impact_usd: float = Field(..., ge=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str]
    recommended_action: str
    auto_fixable: bool
    config_change: Optional[ConfigChange] = None


class PatternSummary(BaseModel):
    total_patterns: int = Field(..., ge=0)
    auto_fixable_patterns: int = Field(..., ge=0)
    potential_recoverable_discrepancies: int = Field(..., ge=0)
    potential_recoverable_value_usd: float = Field(..., ge=0)


class PatternDetectionResponse(BaseModel):
    patterns_detected: list[DetectedPattern]
    summary: PatternSummary
    ai_generated: bool


class AnomalyItem(BaseModel):
    anomaly_id: str
    type: str
    severity: Literal["low", "medium", "high"]
    description: str
    affected_record: Optional[str] = None
    affected_records_count: Optional[int] = Field(default=None, ge=0)
    recommendation: str
    financial_impact_usd: Optional[float] = Field(default=None, ge=0)


class AnomalyDetectionResponse(BaseModel):
    anomalies: list[AnomalyItem]
    analyzed_records: int = Field(..., ge=0)
    analysis_period: str
    ai_generated: bool


class AIStatusResponse(BaseModel):
    ai_enabled: bool
    model: Optional[str] = None
    features: list[str]
