"""
Trains the retry-timing model on SYNTHETIC data (see app/synthetic_retry_data.py
for exactly what that means and why). Run with:

    python -m scripts.train_retry_model

Produces two files under app/ml_artifacts/:
  - retry_model.joblib       the trained classifier
  - retry_model_meta.json    feature order, decline-code encoding, training
                              metadata, and an explicit is_synthetic flag so
                              nothing downstream can accidentally treat this as
                              a model trained on real outcomes.

To retrain on real data once it exists: replace the call to
generate_synthetic_dataset() below with a query against app.models.RecoveryAction
joined to FailedInvoice (recovered vs. not, at what attempt/time), keeping the
same feature columns, and flip is_synthetic to False in the saved metadata.
"""
import json
import os
from datetime import datetime

import joblib
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from app.synthetic_retry_data import generate_synthetic_dataset, DECLINE_CODES

ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "ml_artifacts")
MODEL_PATH = os.path.join(ARTIFACT_DIR, "retry_model.joblib")
META_PATH = os.path.join(ARTIFACT_DIR, "retry_model_meta.json")

NUMERIC_FEATURES = [
    "attempt_number", "health_score", "days_active_30d",
    "hour_of_day", "day_of_week", "is_payday_window", "amount_cents",
]
CATEGORICAL_FEATURES = ["decline_code"]
ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def train(n_samples: int = 20000, seed: int = 42) -> None:
    print(f"Generating {n_samples} synthetic rows (seed={seed})...")
    df = generate_synthetic_dataset(n=n_samples, seed=seed)
    print(f"  {len(df)} rows after excluding non-retryable failure domains")
    print(f"  base recovery rate in synthetic data: {df['recovered'].mean():.3f}")

    X = df[ALL_FEATURES]
    y = df["recovered"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )

    preprocessor = ColumnTransformer([
        ("decline_code", OneHotEncoder(categories=[DECLINE_CODES], handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ], remainder="passthrough")

    pipeline = Pipeline([
        ("preprocess", preprocessor),
        ("model", HistGradientBoostingClassifier(max_iter=150, max_depth=4, random_state=seed)),
    ])

    print("Training HistGradientBoostingClassifier...")
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_proba)
    acc = accuracy_score(y_test, y_pred)

    print(f"\nTest AUC:      {auc:.4f}")
    print(f"Test accuracy: {acc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["not_recovered", "recovered"]))

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)

    metadata = {
        "is_synthetic": True,
        "warning": (
            "Trained entirely on simulated labels (app/synthetic_retry_data.py), "
            "not real recovery outcomes. Treat as a pipeline demonstration, not a "
            "source of real predictive lift over retry_rules.py. See README Step 12."
        ),
        "trained_at": datetime.utcnow().isoformat(),
        "n_samples": n_samples,
        "features": ALL_FEATURES,
        "decline_codes": DECLINE_CODES,
        "test_auc": round(auc, 4),
        "test_accuracy": round(acc, 4),
    }
    with open(META_PATH, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved model to {os.path.abspath(MODEL_PATH)}")
    print(f"Saved metadata to {os.path.abspath(META_PATH)}")


if __name__ == "__main__":
    train()
