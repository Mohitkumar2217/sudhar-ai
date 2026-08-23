"""
Rule-based retry scheduling and network-compliance guardrails.

The full spec trains a LightGBM model on issuer clearing windows. For an MVP with
no historical training data, a heuristic table is more honest and easier to defend
in a demo than a model fit on synthetic data pretending to be real signal.
"""
from datetime import datetime, timedelta

# Hours to wait before each retry attempt (industry-typical soft-decline backoff)
RETRY_BACKOFF_HOURS = {1: 24, 2: 72, 3: 120}
MAX_ATTEMPTS = 4
MAX_RECOVERY_WINDOW_DAYS = 14

# Card networks fine merchants for excessive retries on hard-declined cards.
NON_RETRYABLE_ISO_CODES = {"04", "14", "41", "43", "54"}


def next_retry_at(attempt_count: int, now: datetime | None = None) -> datetime:
    now = now or datetime.utcnow()
    hours = RETRY_BACKOFF_HOURS.get(attempt_count, 120)
    target = now + timedelta(hours=hours)
    # Clamp to a morning UTC slot, roughly aligned with issuer settlement batches.
    return target.replace(hour=7, minute=30, second=0, microsecond=0)


def is_retry_permissible(attempt_count: int, days_in_recovery: int, iso_code: str) -> bool:
    if iso_code in NON_RETRYABLE_ISO_CODES:
        return False
    if attempt_count >= MAX_ATTEMPTS or days_in_recovery > MAX_RECOVERY_WINDOW_DAYS:
        return False
    return True
