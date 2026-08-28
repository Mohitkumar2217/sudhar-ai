"""
Trains the retry-timing model. Defaults to SYNTHETIC data (see
app/synthetic_retry_data.py). Once real RecoveryAction rows exist, switch to
real data:

    python -m scripts.train_retry_model                # synthetic (default)
    python -m scripts.train_retry_model --source real   # real accumulated data

Produces two files under app/ml_artifacts/:
  - retry_model.joblib       the trained classifier
  - retry_model_meta.json    feature order, decline-code encoding, training
                              metadata, and an explicit is_synthetic flag so
                              nothing downstream can accidentally treat a
                              synthetic model as trained on real outcomes.
"""
import argparse
import json
import os
from datetime import datetime

import joblib
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, accuracy_score, classification_report, brier_score_loss
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from app.synthetic_retry_data import generate_synthetic_dataset, DECLINE_CODES
from app.decline_taxonomy import RootCauseDiagnosticEngine

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "ml_artifacts")
MODEL_PATH = os.path.join(ARTIFACT_DIR, "retry_model.joblib")
META_PATH = os.path.join(ARTIFACT_DIR, "retry_model_meta.json")

NUMERIC_FEATURES = [
    "attempt_number", "health_score", "days_active_30d",
    "hour_of_day", "day_of_week", "is_payday_window", "amount_cents",
]
CATEGORICAL_FEATURES = ["decline_code"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def _build_pipeline(seed: int) -> Pipeline:
    preprocessor = ColumnTransformer([
        ("decline_code", OneHotEncoder(categories=[DECLINE_CODES], handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ], remainder="passthrough")
    return Pipeline([
        ("preprocess", preprocessor),
        ("model", HistGradientBoostingClassifier(max_iter=150, max_depth=4, random_state=seed)),
    ])


def _evaluate(pipeline, X_test, y_test) -> dict:
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]
    metrics = {
        "auc": round(roc_auc_score(y_test, y_proba), 4),
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        # Calibration matters here specifically because predict_best_retry_delay_hours()
        # uses the raw probability to RANK candidate hours, not just the class label —
        # a well-ranking but poorly-calibrated model still picks reasonable delays wrong.
        "brier_score": round(brier_score_loss(y_test, y_proba), 4),
    }
    print(f"\nTest AUC:          {metrics['auc']}")
    print(f"Test accuracy:      {metrics['accuracy']}")
    print(f"Test Brier score:   {metrics['brier_score']}  (lower is better-calibrated, 0=perfect, 0.25=random)")
    print(classification_report(y_test, y_pred, target_names=["not_recovered", "recovered"]))
    return metrics


def train_on_synthetic(n_samples: int = 20000, seed: int = 42) -> None:
    print(f"Generating {n_samples} synthetic rows (seed={seed})...")
    df = generate_synthetic_dataset(n=n_samples, seed=seed)
    print(f"  {len(df)} rows after excluding non-retryable failure domains")
    print(f"  base recovery rate in synthetic data: {df['recovered'].mean():.3f}")

    X, y = df[ALL_FEATURES], df["recovered"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=seed, stratify=y)

    pipeline = _build_pipeline(seed)
    print("Training HistGradientBoostingClassifier...")
    pipeline.fit(X_train, y_train)
    metrics = _evaluate(pipeline, X_test, y_test)

    _save(pipeline, metrics, n_samples, is_synthetic=True)


def train_on_real(seed: int = 42) -> None:
    from app.db import SessionLocal
    from app.real_retry_data import extract_real_dataset, time_based_split, InsufficientDataError

    db = SessionLocal()
    try:
        print("Extracting real RecoveryAction data...")
        df = extract_real_dataset(db)
    except InsufficientDataError as e:
        print(f"\n{e}")
        return
    finally:
        db.close()

    print(f"  {len(df)} real retry-attempt rows found")
    print(f"  real recovery rate observed: {df['recovered'].mean():.3f}")

    train_df, test_df = time_based_split(df)
    print(f"  time-based split: {len(train_df)} train (earlier) / {len(test_df)} test (most recent)")
    X_train, y_train = train_df[ALL_FEATURES], train_df["recovered"]
    X_test, y_test = test_df[ALL_FEATURES], test_df["recovered"]

    pipeline = _build_pipeline(seed)
    print("Training HistGradientBoostingClassifier on real data...")
    pipeline.fit(X_train, y_train)
    metrics = _evaluate(pipeline, X_test, y_test)

    _save(pipeline, metrics, len(df), is_synthetic=False)


def _save(pipeline, metrics: dict, n_samples: int, is_synthetic: bool) -> None:
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)

    metadata = {
        "is_synthetic": is_synthetic,
        "warning": (
            "Trained entirely on simulated labels (app/synthetic_retry_data.py), "
            "not real recovery outcomes. Treat as a pipeline demonstration, not a "
            "source of real predictive lift over retry_rules.py. See README Step 12."
            if is_synthetic else
            "Trained on real RecoveryAction outcomes. Verify sample size and test "
            "metrics above are acceptable before enabling RETRY_MODEL_ENABLED in "
            "any environment that affects real customers. See README Step 12 roadmap."
        ),
        "trained_at": datetime.utcnow().isoformat(),
        "n_samples": n_samples,
        "features": ALL_FEATURES,
        "decline_codes": DECLINE_CODES,
        **{f"test_{k}": v for k, v in metrics.items()},
    }
    with open(META_PATH, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved model to {os.path.abspath(MODEL_PATH)}")
    print(f"Saved metadata to {os.path.abspath(META_PATH)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["synthetic", "real"], default="synthetic")
    parser.add_argument("--n-samples", type=int, default=20000, help="synthetic only")
    args = parser.parse_args()

    if args.source == "synthetic":
        train_on_synthetic(n_samples=args.n_samples)
    else:
        train_on_real()
