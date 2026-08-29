import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load .env from the backend folder before reading DATABASE_URL so the seed script
# and any app import behave the same as the FastAPI app.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Defaults to a local SQLite file so you can run this immediately with no
# infra setup. Point DATABASE_URL at Postgres (see schema.sql) for real deployment,
# e.g. postgresql+psycopg2://user:pass@host:5432/revenuerescue
DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./revenuerescue.db"

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
