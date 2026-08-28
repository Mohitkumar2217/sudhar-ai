from dotenv import load_dotenv
load_dotenv()  # MUST run before any app.* import — several modules (llm.py,
                # db.py) read os.getenv(...) at import time, so loading .env
                # after those imports would be too late to affect them.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.routers import invoices, dashboard, copilot, webhooks, portal, model_status
from app import webhook_models  # noqa: F401 — registers WebhookEvent table with Base.metadata

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sudhar AI — MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoices.router)
app.include_router(dashboard.router)
app.include_router(copilot.router)
app.include_router(webhooks.router)
app.include_router(portal.router)
app.include_router(model_status.router)


@app.get("/")
def health():
    return {"status": "ok", "service": "sudhar-ai-mvp"}
