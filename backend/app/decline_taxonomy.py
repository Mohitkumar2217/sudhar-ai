"""
Deterministic root-cause classification for payment declines.
Kept rule-based on purpose: this is a small, auditable lookup table, not something
that benefits from an ML model or an LLM call. Ported from the original architecture
spec's Module 4 with the churn-override heuristic intact.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any


class FailureDomain(str, Enum):
    HARD_DECLINE = "HARD_DECLINE"
    SOFT_DECLINE = "SOFT_DECLINE"
    TECH_FAILURE = "TECHNICAL_FAILURE"
    CHURN_SUSPECT = "DISPUTED_CHURN"


@dataclass
class DiagnosticResult:
    iso_code: str
    failure_domain: FailureDomain
    can_retry_gateway: bool
    requires_card_update: bool
    estimated_recovery_rate: float
    forensic_summary: str


class RootCauseDiagnosticEngine:
    DECLINE_REGISTRY: Dict[str, Dict[str, Any]] = {
        "insufficient_funds":     {"iso": "51", "domain": FailureDomain.SOFT_DECLINE, "retry": True,  "update": False, "rate": 0.68},
        "card_velocity_exceeded": {"iso": "65", "domain": FailureDomain.SOFT_DECLINE, "retry": True,  "update": False, "rate": 0.55},
        "try_again_later":        {"iso": "91", "domain": FailureDomain.TECH_FAILURE, "retry": True,  "update": False, "rate": 0.82},
        "processing_error":       {"iso": "96", "domain": FailureDomain.TECH_FAILURE, "retry": True,  "update": False, "rate": 0.75},
        "expired_card":           {"iso": "54", "domain": FailureDomain.HARD_DECLINE, "retry": False, "update": True,  "rate": 0.35},
        "lost_card":               {"iso": "41", "domain": FailureDomain.HARD_DECLINE, "retry": False, "update": True,  "rate": 0.15},
        "stolen_card":             {"iso": "43", "domain": FailureDomain.HARD_DECLINE, "retry": False, "update": True,  "rate": 0.10},
        "do_not_honor":            {"iso": "05", "domain": FailureDomain.SOFT_DECLINE, "retry": True,  "update": False, "rate": 0.30},
        "pickup_card":             {"iso": "04", "domain": FailureDomain.HARD_DECLINE, "retry": False, "update": True,  "rate": 0.05},
    }

    @classmethod
    def analyze(cls, raw_code: str, customer_health_score: float, active_days_30d: int) -> DiagnosticResult:
        normalized_code = raw_code.lower().strip()
        metadata = cls.DECLINE_REGISTRY.get(
            normalized_code,
            {"iso": "05", "domain": FailureDomain.SOFT_DECLINE, "retry": True, "update": False, "rate": 0.30},
        )

        domain = metadata["domain"]
        recovery_rate = metadata["rate"]
        summary = f"Mapped decline code '{raw_code}' to ISO 8583 code {metadata['iso']}."

        # Behavioral churn override: low engagement + low health score suggests
        # deliberate payment abandonment rather than a fixable payment problem.
        #
        # Direction validated (not the exact thresholds below) against real Telco
        # churn data: churn rate falls from 56% (0-3mo tenure) to 14% (25mo+), and
        # from 43% (month-to-month) to 2.8% (two-year contracts) — see
        # scripts/analyze_churn_correlations.py. Different domain (SaaS days-active
        # vs. telecom tenure/contract), so this confirms the ASSUMPTION that low
        # engagement predicts churn is grounded in real data, not that these
        # specific cutoffs (3 days, 0.30 score) are individually correct.
        if active_days_30d < 3 and customer_health_score < 0.30:
            domain = FailureDomain.CHURN_SUSPECT
            summary += " Low recent activity suggests likely voluntary churn, not a fixable payment issue."
            recovery_rate *= 0.40

        return DiagnosticResult(
            iso_code=metadata["iso"],
            failure_domain=domain,
            can_retry_gateway=metadata["retry"],
            requires_card_update=metadata["update"],
            estimated_recovery_rate=round(recovery_rate, 2),
            forensic_summary=summary,
        )
