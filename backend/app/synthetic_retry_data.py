"""
Generates SYNTHETIC training data for the retry-timing model.

Read this file before trusting anything downstream of it. There is no public
dataset of "this decline code, retried at this hour, succeeded or not" — payment
processors keep that data internal (see the README for why). So this generates
labels from a simulation instead of observations, built on the same decline-rate
table already used by decline_taxonomy.py, plus a handful of timing effects that
are EXPLICITLY INVENTED — not fit to anything real. They're listed as named
constants below specifically so they're easy to find, question, and replace.

The model trained on this data should be understood as a working *pipeline*
(feature engineering -> train/test split -> model -> serialized artifact ->
inference), not a source of real predictive lift over the retry_rules.py
heuristic. Once app.models.RecoveryAction rows exist from real usage, replace
`generate_synthetic_dataset()` with a query against that table — see
scripts/train_retry_model.py for where that swap happens.
"""
import random
from datetime import datetime, timedelta

import pandas as pd

from app.decline_taxonomy import RootCauseDiagnosticEngine, FailureDomain

# --- Named, explicitly-invented timing effects -----------------------------
# None of these numbers come from data. They encode a plausible-sounding story
# (issuers batch-settle in the morning, cardholders have more available balance
# near payday) so the synthetic labels aren't pure noise — but "plausible" is
# not "true." Replace these the moment real retry outcomes exist.
MORNING_HOURS = range(6, 11)          # 6am-10am
MORNING_BOOST = 1.15
PAYDAY_DAYS = {1, 2, 14, 15, 16, 28, 29, 30, 31}
PAYDAY_BOOST = 1.20
PER_ATTEMPT_DECAY = 0.85              # each attempt beyond the first is less likely to land
NOISE_STDDEV = 0.06                   # per-row random jitter so the label isn't a deterministic function of the rules

DECLINE_CODES = list(RootCauseDiagnosticEngine.DECLINE_REGISTRY.keys())

# Same weighting as app/seed.py, kept in sync intentionally — the synthetic
# training distribution should match the synthetic demo-data distribution.
DECLINE_CODE_WEIGHTS = {
    "insufficient_funds": 30, "expired_card": 15, "do_not_honor": 15,
    "try_again_later": 12, "processing_error": 10, "card_velocity_exceeded": 8,
    "lost_card": 4, "stolen_card": 3, "pickup_card": 3,
}


def _clip(p: float, lo: float = 0.02, hi: float = 0.95) -> float:
    return max(lo, min(hi, p))


def generate_synthetic_dataset(n: int = 20000, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    weights = [DECLINE_CODE_WEIGHTS.get(c, 1) for c in DECLINE_CODES]

    rows = []
    for _ in range(n):
        decline_code = rng.choices(DECLINE_CODES, weights=weights, k=1)[0]
        health_score = round(rng.uniform(0.05, 1.0), 2)
        days_active_30d = rng.randint(0, 30)
        attempt_number = rng.choices([1, 2, 3], weights=[50, 30, 20], k=1)[0]
        hour_of_day = rng.randint(0, 23)
        day_of_month = rng.randint(1, 28)
        day_of_week = rng.randint(0, 6)
        amount_cents = rng.choice([1900, 4900, 9900, 19900, 49900, 99900])

        diagnosis = RootCauseDiagnosticEngine.analyze(decline_code, health_score, days_active_30d)
        base_rate = diagnosis.estimated_recovery_rate

        # Hard declines and churn-suspects are excluded from the retry-timing
        # dataset entirely — retry_rules.py already forbids retrying them, so a
        # timing model has nothing to learn for those rows (see is_retry_permissible).
        if diagnosis.failure_domain in (FailureDomain.HARD_DECLINE, FailureDomain.CHURN_SUSPECT):
            continue

        p = base_rate
        if hour_of_day in MORNING_HOURS:
            p *= MORNING_BOOST
        if day_of_month in PAYDAY_DAYS:
            p *= PAYDAY_BOOST
        p *= PER_ATTEMPT_DECAY ** (attempt_number - 1)
        p += rng.gauss(0, NOISE_STDDEV)
        p = _clip(p)

        recovered = 1 if rng.random() < p else 0

        rows.append({
            "decline_code": decline_code,
            "attempt_number": attempt_number,
            "health_score": health_score,
            "days_active_30d": days_active_30d,
            "hour_of_day": hour_of_day,
            "day_of_week": day_of_week,
            "is_payday_window": 1 if day_of_month in PAYDAY_DAYS else 0,
            "amount_cents": amount_cents,
            "recovered": recovered,
        })

    return pd.DataFrame(rows)
