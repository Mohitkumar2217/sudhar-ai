# data/

`WA_Fn-UseC_-Telco-Customer-Churn.csv` is included (small, ~1MB) — used by
`scripts/analyze_churn_correlations.py`.

`creditcard.csv` (the ULB Credit Card Fraud dataset, ~144MB) is **not included**
in this delivery to keep the zip a reasonable size — it's your own uploaded
file. To retrain `scripts/train_fraud_demo_model.py`, place it here as
`data/creditcard.csv`. The already-trained artifact
(`app/ml_artifacts/fraud_demo_model.joblib`, trained on the real file, real
metrics in `fraud_demo_model_meta.json`) is included and works without it.
