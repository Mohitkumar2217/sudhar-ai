"""
Checks the DIRECTION of decline_taxonomy.py's churn-override heuristic
(low days_active_30d + low health_score -> DISPUTED_CHURN) against real churn
data. Not a calibration of the exact thresholds — telecom subscriber tenure in
months and a Sudhar AI SaaS customer's days_active_30d aren't the same
measurement, and "Contract" (month-to-month/one-year/two-year) has no Sudhar AI
equivalent at all. What this DOES honestly establish: the underlying
assumption that low engagement/tenure correlates with real churn is not an
invented one — it holds clearly in a real, independent dataset.

Run with: python -m scripts.analyze_churn_correlations
"""
import os
import pandas as pd

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "WA_Fn-UseC_-Telco-Customer-Churn.csv")


def run() -> None:
    df = pd.read_csv(DATA_PATH)
    df["Churn_binary"] = (df["Churn"] == "Yes").astype(int)

    print(f"Overall churn rate: {100 * df['Churn_binary'].mean():.1f}%  (n={len(df)})")

    print("\n--- Churn rate by tenure bucket ---")
    df["tenure_bucket"] = pd.cut(
        df["tenure"], bins=[-1, 3, 12, 24, 200], labels=["0-3mo", "4-12mo", "13-24mo", "25mo+"]
    )
    print(df.groupby("tenure_bucket", observed=True)["Churn_binary"].agg(["mean", "count"]))

    print("\n--- Churn rate by contract type ---")
    print(df.groupby("Contract")["Churn_binary"].agg(["mean", "count"]))

    print(
        "\nConclusion: churn rate falls monotonically with tenure and is far lower on "
        "longer contracts — this is real, independent evidence for the DIRECTION of "
        "decline_taxonomy.py's churn override (low engagement -> higher churn risk), "
        "not a source for its exact numeric thresholds (different domain, different units)."
    )


if __name__ == "__main__":
    run()
