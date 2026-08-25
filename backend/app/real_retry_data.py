"""
Extracts REAL training data from accumulated RecoveryAction rows, once enough
exist. This is the Phase 2/3 counterpart to synthetic_retry_data.py — same
feature columns, real labels, real timestamps.

Two things this deliberately gets right that a naive query would get wrong:

1. Uses the SNAPSHOTTED attempt_number/decline_code/health_score columns on
   RecoveryAction (added specifically for this), not a live join to
   FailedInvoice/Customer — those mutate after the action happened, so a live
   join silently mislabels historical rows with post-hoc values.

2. Splits by TIME, not randomly. train_test_split's random shuffle would leak
   later calendar patterns (a payday three months from now) into training,
   making validation look better than the model will actually perform once
   deployed forward in time. Real deployments only ever predict forward.
"""
from datetime import datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RecoveryAction, FailedInvoice

MIN_ROWS_WARNING = 2000  # below this, treat any trained model as unreliable — see README Step 12/roadmap


class InsufficientDataError(Exception):
    pass


def extract_real_dataset(db: Session, min_rows: int = 500) -> pd.DataFrame:
    """Pulls every HEADLESS_RETRY action with a valid snapshot into a training
    row. Raises InsufficientDataError below min_rows rather than silently
    training on too little data — a model trained on 40 rows will report a
    confident-looking AUC that means nothing."""
    rows = db.execute(
        select(
            RecoveryAction.decline_code_snapshot,
            RecoveryAction.attempt_number,
            RecoveryAction.health_score_snapshot,
            RecoveryAction.is_successful,
            RecoveryAction.created_at,
            FailedInvoice.amount_due_cents,
        )
        .join(FailedInvoice, RecoveryAction.invoice_id == FailedInvoice.id)
        .where(
            RecoveryAction.action_type == "HEADLESS_RETRY",
            RecoveryAction.decline_code_snapshot.isnot(None),  # excludes pre-Step-12-fix rows
        )
        .order_by(RecoveryAction.created_at.asc())
    ).all()

    if len(rows) < min_rows:
        raise InsufficientDataError(
            f"Only {len(rows)} usable RecoveryAction rows found (need >= {min_rows}). "
            f"Keep running the recovery engine against real traffic and try again later. "
            f"See README Step 12 roadmap, Phase 1."
        )

    records = []
    for decline_code, attempt_number, health_score, is_successful, created_at, amount_due_cents in rows:
        payday_days = {1, 2, 14, 15, 16, 28, 29, 30, 31}
        records.append({
            "decline_code": decline_code,
            "attempt_number": attempt_number,
            "health_score": float(health_score) if health_score is not None else 0.5,
            "days_active_30d": 15,  # not currently snapshotted — see README Step 12 roadmap, Phase 0 follow-up
            "hour_of_day": created_at.hour,
            "day_of_week": created_at.weekday(),
            "is_payday_window": 1 if created_at.day in payday_days else 0,
            "amount_cents": amount_due_cents,
            "recovered": 1 if is_successful else 0,
            "_created_at": created_at,  # kept for the time-based split, dropped before training
        })

    df = pd.DataFrame(records)
    if len(df) < MIN_ROWS_WARNING:
        print(
            f"WARNING: only {len(df)} rows — below the {MIN_ROWS_WARNING} recommended "
            f"minimum for a trustworthy model. Training will proceed but treat results "
            f"as preliminary, not production-ready."
        )
    return df


def time_based_split(df: pd.DataFrame, test_fraction: float = 0.2):
    """Splits chronologically — train on the earliest (1 - test_fraction), test on
    the most recent slice. This is what actually predicts real-world performance
    for a model that will only ever be asked to forecast forward in time."""
    df_sorted = df.sort_values("_created_at").reset_index(drop=True)
    split_idx = int(len(df_sorted) * (1 - test_fraction))
    train_df = df_sorted.iloc[:split_idx].drop(columns=["_created_at"])
    test_df = df_sorted.iloc[split_idx:].drop(columns=["_created_at"])
    return train_df, test_df
