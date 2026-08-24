"""
Inference wrapper around the retry-timing model trained by
scripts/train_retry_model.py. Loads once, exposes:

  - predict_recovery_probability(...)  probability a retry succeeds at a given time
  - predict_best_retry_delay_hours(...) which of several candidate delays scores highest

Both are used by recovery_engine.py ONLY when RETRY_MODEL_ENABLED=true, and only
if the model artifact actually loads — any failure (missing file, corrupt
artifact) falls back to the retry_rules.py heuristic rather than raising, since
this model is explicitly a synthetic-data pipeline demo, not something the
recovery loop should depend on to function.
"""
import json
import os
from datetime import datetime, timedelta

import joblib
import pandas as pd

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "ml_artifacts")
MODEL_PATH = os.path.join(ARTIFACT_DIR, "retry_model.joblib")
META_PATH = os.path.join(ARTIFACT_DIR, "retry_model_meta.json")

# Same candidate windows retry_rules.py's heuristic backoff table considers,
# so the model and the heuristic are picking from a comparable option set.
CANDIDATE_DELAY_HOURS = [24, 48, 72, 96, 120, 144, 168]

_model = None
_metadata = None
_load_attempted = False


class RetryModelUnavailable(Exception):
    pass


def _load():
    global _model, _metadata, _load_attempted
    if _load_attempted:
        if _model is None:
            raise RetryModelUnavailable("Model previously failed to load.")
        return
    _load_attempted = True
    try:
        _model = joblib.load(MODEL_PATH)
        with open(META_PATH) as f:
            _metadata = json.load(f)
    except (FileNotFoundError, OSError, Exception) as e:
        _model = None
        raise RetryModelUnavailable(
            f"Retry model not available ({e}). Run: python -m scripts.train_retry_model"
        )


def is_synthetic() -> bool:
    """True if the loaded model was trained on simulated labels, not real
    recovery outcomes. Always check this before treating a prediction as
    anything more than a pipeline demonstration."""
    _load()
    return bool(_metadata.get("is_synthetic", True))


def predict_recovery_probability(
    decline_code: str,
    attempt_number: int,
    health_score: float,
    days_active_30d: int,
    at: datetime,
    amount_cents: int,
) -> float:
    _load()
    day_of_month = at.day
    payday_days = {1, 2, 14, 15, 16, 28, 29, 30, 31}
    row = pd.DataFrame([{
        "decline_code": decline_code,
        "attempt_number": attempt_number,
        "health_score": health_score,
        "days_active_30d": days_active_30d,
        "hour_of_day": at.hour,
        "day_of_week": at.weekday(),
        "is_payday_window": 1 if day_of_month in payday_days else 0,
        "amount_cents": amount_cents,
    }])
    return float(_model.predict_proba(row)[0, 1])


def predict_best_retry_delay_hours(
    decline_code: str,
    attempt_number: int,
    health_score: float,
    days_active_30d: int,
    amount_cents: int,
    now: datetime | None = None,
) -> tuple[int, float]:
    """Scores each candidate delay and returns (best_delay_hours, its_predicted_probability)."""
    now = now or datetime.utcnow()
    scored = [
        (
            hours,
            predict_recovery_probability(
                decline_code, attempt_number, health_score, days_active_30d,
                now + timedelta(hours=hours), amount_cents,
            ),
        )
        for hours in CANDIDATE_DELAY_HOURS
    ]
    return max(scored, key=lambda pair: pair[1])
