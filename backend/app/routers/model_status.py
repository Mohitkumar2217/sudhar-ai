import json
import os

from fastapi import APIRouter

router = APIRouter(prefix="/model", tags=["model"])

META_PATH = os.path.join(os.path.dirname(__file__), "..", "ml_artifacts", "retry_model_meta.json")
RETRY_MODEL_ENABLED = os.getenv("RETRY_MODEL_ENABLED", "false").lower() == "true"


@router.get("/status")
def model_status():
    """Surfaces what's actually loaded, since RETRY_MODEL_ENABLED and 'a model
    file exists' are independent facts — this endpoint tells the dashboard both,
    plus whether that model was trained on synthetic or real data (see README
    Step 12), so the UI can't accidentally present a synthetic model as if it
    were validated on real outcomes."""
    if not os.path.exists(META_PATH):
        return {"trained": False, "enabled": RETRY_MODEL_ENABLED, "active": False}

    with open(META_PATH) as f:
        meta = json.load(f)

    return {
        "trained": True,
        "enabled": RETRY_MODEL_ENABLED,
        "active": RETRY_MODEL_ENABLED,  # a trained model only actually affects scheduling if the flag is also on
        "is_synthetic": meta.get("is_synthetic", True),
        "trained_at": meta.get("trained_at"),
        "n_samples": meta.get("n_samples"),
        "test_auc": meta.get("test_auc"),
        "test_accuracy": meta.get("test_accuracy"),
        "test_brier_score": meta.get("test_brier_score"),
    }
