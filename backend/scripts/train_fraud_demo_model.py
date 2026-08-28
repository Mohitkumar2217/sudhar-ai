"""
Trains a fraud classifier on the real ULB credit card fraud dataset
(data/creditcard.csv — 284,807 real transactions, 492 confirmed fraud, genuine
`Class` label). This is a real, verifiable ML exercise: real data, real label,
real metrics below.

READ THIS BEFORE WIRING IT INTO ANYTHING: this model's features are V1-V28
(PCA-anonymized components from an unrelated card network's transaction data)
plus Amount and Time. Sudhar AI's own FailedInvoice rows have none of those —
there is no way to compute a V1-V28 vector for a Sudhar AI transaction, because
the PCA transform that produced them was fit on a different dataset entirely
and was never published. This model CANNOT take a FailedInvoice as input.

What it's actually good for: a real, honest demonstration that a fraud
classifier trained on the classic public benchmark works as expected (this
exact dataset produces near-perfect metrics in essentially every published
result — high AUC here confirms the pipeline is right, not that anything new
was discovered). For a fraud signal that actually integrates with Sudhar AI's
recovery loop, see app/fraud_heuristic.py instead — that one uses Sudhar AI's
real schema, at the cost of being a heuristic rather than a trained model,
because no labeled fraud data exists for Sudhar AI's own transactions.

Run with: python -m scripts.train_fraud_demo_model
"""
import json
import os
from datetime import datetime

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    roc_auc_score, average_precision_score, precision_recall_fscore_support,
    classification_report,
)
from sklearn.model_selection import train_test_split

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "creditcard.csv")
ARTIFACT_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "ml_artifacts")
MODEL_PATH = os.path.join(ARTIFACT_DIR, "fraud_demo_model.joblib")
META_PATH = os.path.join(ARTIFACT_DIR, "fraud_demo_model_meta.json")

FEATURES = [f"V{i}" for i in range(1, 29)] + ["Amount"]


def train(seed: int = 42) -> None:
    print(f"Loading {DATA_PATH}...")
    df = pd.read_csv(DATA_PATH)
    fraud_rate = df["Class"].mean()
    print(f"  {len(df)} rows, {df['Class'].sum()} fraud ({fraud_rate*100:.4f}%)")

    X, y = df[FEATURES], df["Class"]
    # Stratified split is essential here — with 0.17% positives, a random split
    # without stratification risks a test set with zero (or near-zero) fraud
    # examples, making every metric below meaningless.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y
    )

    # class_weight="balanced" matters more than usual here — without it, a
    # model can get 99.8% accuracy by predicting "not fraud" for everything,
    # which is exactly the failure mode plain accuracy would hide.
    model = HistGradientBoostingClassifier(
        max_iter=200, max_depth=6, random_state=seed, class_weight="balanced"
    )
    print("Training HistGradientBoostingClassifier (class_weight=balanced)...")
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, y_proba)
    # Average precision (area under precision-recall curve) matters more than
    # ROC-AUC on this imbalanced a dataset — ROC-AUC can look deceptively good
    # even with a fairly weak model when negatives this overwhelmingly outnumber
    # positives.
    ap = average_precision_score(y_test, y_proba)
    precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="binary")

    print(f"\nTest ROC-AUC:        {auc:.4f}")
    print(f"Test Avg Precision:  {ap:.4f}  (more meaningful than AUC at this class imbalance)")
    print(f"Test Precision:      {precision:.4f}")
    print(f"Test Recall:         {recall:.4f}")
    print(f"Test F1:             {f1:.4f}")
    print(classification_report(y_test, y_pred, target_names=["legitimate", "fraud"]))

    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    metadata = {
        "dataset": "ULB Credit Card Fraud Detection (creditcard.csv)",
        "dataset_source": "real, labeled, publicly released fraud data",
        "compatible_with_sudhar_schema": False,
        "warning": (
            "Trained on V1-V28 PCA-anonymized features from an unrelated card "
            "network. Cannot score a Sudhar AI FailedInvoice — no equivalent "
            "features exist for Sudhar AI transactions. Demonstration/reference "
            "only. See app/fraud_heuristic.py for the model that actually "
            "integrates with the recovery engine."
        ),
        "trained_at": datetime.utcnow().isoformat(),
        "n_samples": len(df),
        "n_fraud": int(df["Class"].sum()),
        "fraud_rate": round(fraud_rate, 6),
        "features": FEATURES,
        "test_auc": round(auc, 4),
        "test_average_precision": round(ap, 4),
        "test_precision": round(precision, 4),
        "test_recall": round(recall, 4),
        "test_f1": round(f1, 4),
    }
    with open(META_PATH, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\nSaved model to {os.path.abspath(MODEL_PATH)}")
    print(f"Saved metadata to {os.path.abspath(META_PATH)}")


if __name__ == "__main__":
    train()
