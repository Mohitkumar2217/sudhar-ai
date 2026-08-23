from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.routers import invoices, dashboard, copilot

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


@app.get("/")
def health():
    return {"status": "ok", "service": "sudhar-ai"}
