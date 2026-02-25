"""
AI-powered analysis service using Claude API.
Provides intelligent explanations, root cause analysis, and recommendations.
"""
import json
import re
from typing import Optional
from datetime import datetime
from anthropic import AsyncAnthropic

from app.config import settings


class AIAnalysisService:
    """Service for AI-powered reconciliation analysis."""

    def __init__(self):
        self.client = None
        if settings.ANTHROPIC_API_KEY and settings.AI_ANALYSIS_ENABLED:
            self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.CLAUDE_MODEL

    @property
    def is_available(self) -> bool:
        """Check if AI analysis is available."""
        return self.client is not None

    # === MAIN ANALYSIS METHODS ===

    async def explain_match(
        self,
        match_result: dict,
        transaction: dict,
        settlement: Optional[dict] = None,
        adjustment: Optional[dict] = None
    ) -> dict:
        """Generate human-readable explanation for a match."""
        if not self.is_available:
            return self._fallback_match_explanation(match_result)

        prompt = self._build_match_explanation_prompt(
            match_result, transaction, settlement, adjustment
        )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=settings.AI_MAX_TOKENS,
            temperature=settings.AI_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_match_explanation(response.content[0].text, match_result)

    async def analyze_discrepancy(
        self,
        discrepancy: dict,
        related_records: dict,
        suggested_matches: list[dict]
    ) -> dict:
        """Analyze why a record is unmatched and identify root causes."""
        if not self.is_available:
            return self._fallback_discrepancy_analysis(discrepancy)

        prompt = self._build_discrepancy_analysis_prompt(
            discrepancy, related_records, suggested_matches
        )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=settings.AI_MAX_TOKENS,
            temperature=settings.AI_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_discrepancy_analysis(response.content[0].text, discrepancy)

    async def rank_suggestions(
        self,
        unmatched_record: dict,
        candidates: list[dict]
    ) -> dict:
        """Use AI to rank and explain potential matches."""
        if not self.is_available or not candidates:
            return {
                "unmatched_record": unmatched_record,
                "ai_ranked_suggestions": candidates,
                "ai_generated": False
            }

        prompt = self._build_suggestion_ranking_prompt(unmatched_record, candidates)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=settings.AI_MAX_TOKENS,
            temperature=settings.AI_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_ranked_suggestions(response.content[0].text, unmatched_record, candidates)

    async def generate_summary(
        self,
        stats: dict,
        discrepancies: list[dict],
        high_priority_items: list[dict]
    ) -> dict:
        """Generate executive summary of reconciliation results."""
        if not self.is_available:
            return self._fallback_summary(stats)

        prompt = self._build_summary_prompt(stats, discrepancies, high_priority_items)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            temperature=settings.AI_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_summary(response.content[0].text, stats)

    async def detect_patterns(
        self,
        discrepancies: list[dict],
        time_range_days: int = 30,
        min_occurrences: int = 3
    ) -> dict:
        """Identify systemic patterns across discrepancies."""
        if not self.is_available:
            return {"patterns_detected": [], "summary": {"total_patterns": 0, "auto_fixable_patterns": 0, "potential_recoverable_discrepancies": 0, "potential_recoverable_value_usd": 0}, "ai_generated": False}

        prompt = self._build_pattern_detection_prompt(
            discrepancies, time_range_days, min_occurrences
        )

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            temperature=settings.AI_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_patterns(response.content[0].text)

    async def detect_anomalies(
        self,
        matches: list[dict],
        settlements: list[dict],
        adjustments: list[dict]
    ) -> dict:
        """Detect unusual patterns that may indicate issues."""
        if not self.is_available:
            return {"anomalies": [], "analyzed_records": 0, "analysis_period": "7 days", "ai_generated": False}

        stats = self._calculate_anomaly_stats(matches, settlements, adjustments)
        prompt = self._build_anomaly_detection_prompt(stats)

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=settings.AI_MAX_TOKENS,
            temperature=settings.AI_TEMPERATURE,
            messages=[{"role": "user", "content": prompt}]
        )

        return self._parse_anomalies(response.content[0].text, len(matches) + len(settlements))

    # === PROMPT BUILDERS ===

    def _build_match_explanation_prompt(self, match: dict, txn: dict, stl: Optional[dict], adj: Optional[dict]) -> str:
        """Build prompt for match explanation."""
        matched_record_type = "SETTLEMENT" if stl else "ADJUSTMENT"
        matched_data = stl if stl else adj

        return f"""You are a payment reconciliation expert. Explain why these records matched.

TRANSACTION:
{json.dumps(txn, indent=2, default=str)}

{matched_record_type}:
{json.dumps(matched_data, indent=2, default=str)}

MATCH RESULT:
- Confidence Score: {match.get('confidence_score', match.get('confidence', 0))}%
- Match Reasons: {match.get('match_reasons', [])}
- Amount Difference: {match.get('amount_difference', 0)}
- Date Difference: {match.get('date_difference_days', 0)} days

Provide a JSON response with this exact structure:
{{
  "explanation": "2-3 sentence explanation of why these matched",
  "confidence_breakdown": {{
    "factor_name": {{"contribution": points_as_int, "detail": "explanation"}}
  }},
  "warnings": ["any concerns about this match"],
  "recommendation": "approve|review|reject"
}}

Be specific about the numbers. Explain fee deductions, timing, and any ID matching details."""

    def _build_discrepancy_analysis_prompt(self, disc: dict, records: dict, suggestions: list) -> str:
        """Build prompt for discrepancy analysis."""
        return f"""You are a payment reconciliation expert. Analyze why this record is unmatched.

DISCREPANCY:
{json.dumps(disc, indent=2, default=str)}

RELATED RECORDS:
{json.dumps(records, indent=2, default=str)}

POTENTIAL MATCHES (rule-based):
{json.dumps(suggestions[:5], indent=2, default=str) if suggestions else "None found"}

Provide a JSON response with this exact structure:
{{
  "summary": "1-2 sentence summary of the issue",
  "root_cause_probabilities": [
    {{"cause": "description", "probability": 0.0_to_1.0, "evidence": ["supporting facts"]}}
  ],
  "investigation_priority": "high|medium|low",
  "priority_reasoning": "why this priority",
  "suggested_actions": [
    {{"action": "specific step", "confidence": "high|medium|low", "reasoning": "why"}}
  ],
  "potential_matches": [
    {{"transaction_id": "id_or_null", "settlement_id": "id_or_null", "current_confidence": 0, "missing_factors": [], "ai_confidence": 0_to_100, "ai_reasoning": "why it might match"}}
  ]
}}

Consider: missing references, ID truncation, fee variations, timing issues, currency mismatches."""

    def _build_suggestion_ranking_prompt(self, unmatched: dict, candidates: list) -> str:
        """Build prompt for ranking match suggestions."""
        return f"""You are a payment reconciliation expert. Rank these potential matches.

UNMATCHED RECORD:
{json.dumps(unmatched, indent=2, default=str)}

CANDIDATE MATCHES:
{json.dumps(candidates, indent=2, default=str)}

Provide a JSON response:
{{
  "rankings": [
    {{
      "candidate_id": "id from candidates",
      "rule_based_confidence": original_score_int,
      "ai_confidence": your_score_0_to_100,
      "reasoning": "detailed explanation of match likelihood",
      "recommended_action": "action to take"
    }}
  ]
}}

Consider factors rules might miss: bank-specific patterns, merchant context, historical matching."""

    def _build_summary_prompt(self, stats: dict, discrepancies: list, high_priority: list) -> str:
        """Build prompt for executive summary."""
        return f"""You are a payment reconciliation expert writing an executive summary.

RECONCILIATION STATISTICS:
{json.dumps(stats, indent=2, default=str)}

DISCREPANCY BREAKDOWN (sample):
{json.dumps(discrepancies[:10], indent=2, default=str)}

HIGH PRIORITY ITEMS: {len(high_priority)} items

Write an executive summary in markdown format including:
1. OVERALL HEALTH: One-line assessment (Good/Concerning/Critical)
2. KEY FINDINGS: 3-4 bullet points
3. CONCERNS: Issues requiring attention
4. RECOMMENDED ACTIONS: Specific next steps

Use specific numbers. Keep it under 300 words. Write for a finance manager."""

    def _build_pattern_detection_prompt(self, discrepancies: list, time_range: int, min_occurrences: int) -> str:
        """Build prompt for pattern detection."""
        return f"""You are a payment reconciliation expert identifying systemic issues.

DISCREPANCIES (last {time_range} days):
{json.dumps(discrepancies[:30], indent=2, default=str)}

Find patterns appearing {min_occurrences}+ times. Look for:
- Bank-specific settlement delays
- Reference format issues by processor
- Fee variations by payment method
- Currency-specific problems

Provide JSON:
{{
  "patterns_detected": [
    {{
      "pattern_id": "pat_001",
      "pattern_type": "settlement_delay|reference_truncation|fee_anomaly|other",
      "description": "clear description",
      "affected_discrepancies": count_int,
      "financial_impact_usd": estimated_amount_float,
      "confidence": 0.0_to_1.0,
      "evidence": ["specific facts"],
      "recommended_action": "what to do",
      "auto_fixable": true_or_false,
      "config_change": {{"setting": "name", "scope": "scope", "current_value": "x", "recommended_value": "y"}}
    }}
  ],
  "summary": {{
    "total_patterns": count_int,
    "auto_fixable_patterns": count_int,
    "potential_recoverable_discrepancies": count_int,
    "potential_recoverable_value_usd": amount_float
  }}
}}"""

    def _build_anomaly_detection_prompt(self, stats: dict) -> str:
        """Build prompt for anomaly detection."""
        return f"""You are a payment reconciliation expert detecting anomalies.

DATA STATISTICS:
{json.dumps(stats, indent=2, default=str)}

Identify unusual patterns:
- Fees outside normal ranges (2-5% typical)
- Settlement delays beyond normal windows
- Chargeback clusters
- Currency conversion outliers
- Suspicious amount patterns

Provide JSON:
{{
  "anomalies": [
    {{
      "anomaly_id": "anom_001",
      "type": "unusual_fee|settlement_delay|chargeback_cluster|amount_outlier|other",
      "severity": "low|medium|high",
      "description": "clear description with numbers",
      "affected_record": "specific ID if applicable or null",
      "affected_records_count": count_int_or_null,
      "recommendation": "specific action",
      "financial_impact_usd": amount_float_or_null
    }}
  ]
}}"""

    # === FALLBACK METHODS ===

    def _fallback_match_explanation(self, match: dict) -> dict:
        """Rule-based explanation when AI unavailable."""
        reasons = match.get('match_reasons', [])
        confidence = match.get('confidence_score', match.get('confidence', 0))

        explanation = f"Match confidence: {confidence}%. "
        if reasons:
            explanation += f"Matched based on: {', '.join(str(r) for r in reasons)}. "

        return {
            "match_id": str(match.get('id', match.get('match_id', ''))),
            "confidence": confidence,
            "explanation": explanation,
            "confidence_breakdown": {},
            "warnings": [],
            "recommendation": "approve" if confidence >= 80 else "review",
            "ai_generated": False
        }

    def _fallback_discrepancy_analysis(self, disc: dict) -> dict:
        """Rule-based analysis when AI unavailable."""
        return {
            "discrepancy_id": str(disc.get('discrepancy_id', disc.get('id', ''))),
            "discrepancy_type": disc.get('discrepancy_type', 'unknown'),
            "analysis": {
                "summary": "Manual review required - AI analysis unavailable",
                "root_cause_probabilities": [],
                "investigation_priority": disc.get('severity', 'medium'),
                "priority_reasoning": "Default priority based on severity"
            },
            "suggested_actions": disc.get('suggested_actions', []),
            "similar_resolved_cases": [],
            "potential_matches": disc.get('suggested_matches', []),
            "ai_generated": False
        }

    def _fallback_summary(self, stats: dict) -> dict:
        """Rule-based summary when AI unavailable."""
        match_rate = stats.get('match_rate', 0)
        health = "good" if match_rate >= 90 else "concerning" if match_rate >= 80 else "critical"

        return {
            "summary": f"Match rate: {match_rate:.1f}%. Status: {health.upper()}. AI summary unavailable.",
            "health_status": health,
            "match_rate": match_rate,
            "key_metrics": {
                "total_transactions": stats.get('total_transactions', 0),
                "matched": stats.get('matched', 0),
                "unmatched_transactions": stats.get('unmatched_transactions', 0),
                "unmatched_settlements": stats.get('unmatched_settlements', 0),
                "unmatched_adjustments": stats.get('unmatched_adjustments', 0),
                "total_discrepancy_value_usd": stats.get('total_discrepancy_value_usd', 0)
            },
            "high_priority_items": stats.get('high_priority_count', 0),
            "generated_at": datetime.utcnow(),
            "ai_generated": False
        }

    # === HELPER METHODS ===

    def _calculate_anomaly_stats(self, matches: list, settlements: list, adjustments: list) -> dict:
        """Calculate statistics for anomaly detection."""
        fees = []
        for s in settlements:
            if isinstance(s, dict) and s.get('fees_deducted') and s.get('gross_amount'):
                try:
                    fee_pct = (float(s['fees_deducted']) / float(s['gross_amount'])) * 100
                    fees.append({'settlement_id': s.get('settlement_id'), 'fee_pct': fee_pct})
                except (ValueError, ZeroDivisionError):
                    pass

        return {
            "total_matches": len(matches),
            "total_settlements": len(settlements),
            "total_adjustments": len(adjustments),
            "fee_statistics": fees[:20],
            "settlements_sample": [self._safe_dict(s) for s in settlements[:20]],
            "adjustments_sample": [self._safe_dict(a) for a in adjustments[:20]]
        }

    def _safe_dict(self, obj) -> dict:
        """Convert object to dict safely."""
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, '__dict__'):
            return {k: str(v) for k, v in obj.__dict__.items() if not k.startswith('_')}
        return {"value": str(obj)}

    def _parse_match_explanation(self, ai_response: str, match: dict) -> dict:
        """Parse AI response for match explanation."""
        try:
            # Try to extract JSON from response
            parsed = self._extract_json(ai_response)
            return {
                "match_id": str(match.get('id', match.get('match_id', ''))),
                "confidence": match.get('confidence_score', match.get('confidence', 0)),
                "explanation": parsed.get('explanation', ai_response),
                "confidence_breakdown": parsed.get('confidence_breakdown', {}),
                "warnings": parsed.get('warnings', []),
                "recommendation": parsed.get('recommendation', 'review'),
                "ai_generated": True
            }
        except Exception:
            return {
                "match_id": str(match.get('id', match.get('match_id', ''))),
                "confidence": match.get('confidence_score', match.get('confidence', 0)),
                "explanation": ai_response,
                "confidence_breakdown": {},
                "warnings": [],
                "recommendation": "review",
                "ai_generated": True
            }

    def _parse_discrepancy_analysis(self, ai_response: str, disc: dict) -> dict:
        """Parse AI response for discrepancy analysis."""
        try:
            parsed = self._extract_json(ai_response)
            return {
                "discrepancy_id": str(disc.get('discrepancy_id', disc.get('id', ''))),
                "discrepancy_type": disc.get('discrepancy_type', 'unknown'),
                "analysis": {
                    "summary": parsed.get('summary', ai_response),
                    "root_cause_probabilities": parsed.get('root_cause_probabilities', []),
                    "investigation_priority": parsed.get('investigation_priority', 'medium'),
                    "priority_reasoning": parsed.get('priority_reasoning', '')
                },
                "suggested_actions": parsed.get('suggested_actions', []),
                "similar_resolved_cases": [],
                "potential_matches": parsed.get('potential_matches', []),
                "ai_generated": True
            }
        except Exception:
            return self._fallback_discrepancy_analysis(disc)

    def _parse_ranked_suggestions(self, ai_response: str, unmatched: dict, candidates: list) -> dict:
        """Parse AI response for ranked suggestions."""
        try:
            parsed = self._extract_json(ai_response)
            return {
                "unmatched_record": unmatched,
                "ai_ranked_suggestions": parsed.get('rankings', candidates),
                "ai_generated": True
            }
        except Exception:
            return {
                "unmatched_record": unmatched,
                "ai_ranked_suggestions": candidates,
                "ai_generated": False
            }

    def _parse_summary(self, ai_response: str, stats: dict) -> dict:
        """Parse AI response for summary."""
        match_rate = stats.get('match_rate', 0)
        health = "good" if match_rate >= 90 else "concerning" if match_rate >= 80 else "critical"

        return {
            "summary": ai_response,
            "health_status": health,
            "match_rate": match_rate,
            "key_metrics": {
                "total_transactions": stats.get('total_transactions', 0),
                "matched": stats.get('matched', 0),
                "unmatched_transactions": stats.get('unmatched_transactions', 0),
                "unmatched_settlements": stats.get('unmatched_settlements', 0),
                "unmatched_adjustments": stats.get('unmatched_adjustments', 0),
                "total_discrepancy_value_usd": stats.get('total_discrepancy_value_usd', 0)
            },
            "high_priority_items": stats.get('high_priority_count', 0),
            "generated_at": datetime.utcnow(),
            "ai_generated": True
        }

    def _parse_patterns(self, ai_response: str) -> dict:
        """Parse AI response for pattern detection."""
        try:
            parsed = self._extract_json(ai_response)
            return {
                "patterns_detected": parsed.get('patterns_detected', []),
                "summary": parsed.get('summary', {"total_patterns": 0, "auto_fixable_patterns": 0, "potential_recoverable_discrepancies": 0, "potential_recoverable_value_usd": 0}),
                "ai_generated": True
            }
        except Exception:
            return {"patterns_detected": [], "summary": {"total_patterns": 0, "auto_fixable_patterns": 0, "potential_recoverable_discrepancies": 0, "potential_recoverable_value_usd": 0}, "ai_generated": False}

    def _parse_anomalies(self, ai_response: str, record_count: int) -> dict:
        """Parse AI response for anomaly detection."""
        try:
            parsed = self._extract_json(ai_response)
            return {
                "anomalies": parsed.get('anomalies', []),
                "analyzed_records": record_count,
                "analysis_period": "7 days",
                "ai_generated": True
            }
        except Exception:
            return {
                "anomalies": [],
                "analyzed_records": record_count,
                "analysis_period": "7 days",
                "ai_generated": False
            }

    def _extract_json(self, text: str) -> dict:
        """Extract JSON from text that may contain markdown code blocks."""
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            return json.loads(json_match.group(1))

        # Try to find JSON object in text
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group(0))

        raise ValueError("No JSON found in response")
