import json
import os
import re

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.llm import synthesize_copilot_answer, call_llm

router = APIRouter(prefix="/copilot", tags=["copilot"])

SCHEMA_DESCRIPTION = """
Table: failed_invoices
Columns: id, tenant_id, customer_id, invoice_id, amount_due_cents, currency,
         raw_decline_code, iso_8583_code, failure_type, status, attempt_count,
         next_action_scheduled_at, recovered_at, created_at

Table: customers
Columns: id, tenant_id, external_customer_id, email, name, mrr_cents,
         health_score, days_active_past_30d

Table: recovery_actions
Columns: id, invoice_id, action_type, channel, is_successful, created_at
"""

# Same safety rule as the original spec: block any mutation statement outright.
FORBIDDEN_TOKENS = ["DROP", "DELETE", "ALTER", "TRUNCATE", "INSERT", "UPDATE", "CREATE", "ATTACH", "DETACH", "PRAGMA"]


class CopilotRequest(BaseModel):
    question: str


def sanitize_sql(sql: str) -> str:
    for token in FORBIDDEN_TOKENS:
        if re.search(r"\b" + token + r"\b", sql, re.IGNORECASE):
            raise ValueError(f"Query blocked: contains prohibited statement '{token}'.")
    if not re.match(r"^\s*SELECT", sql, re.IGNORECASE):
        raise ValueError("Only SELECT queries are permitted.")
    return sql


FALLBACK_SQL = "SELECT status, COUNT(*) as count FROM failed_invoices GROUP BY status"


def generate_sql(question: str) -> str:
    prompt = f"""Generate ONLY a valid SQL SELECT query (SQLite/Postgres-compatible) for this schema:
{SCHEMA_DESCRIPTION}

Question: {question}
Output only the raw SQL inside a ```sql code block. No explanation."""

    raw = call_llm(prompt, max_tokens=300)
    if not raw:
        # Offline fallback: a safe, generic query so the endpoint stays testable
        # without an API key, and the same path a billing/rate-limit/network
        # failure falls back to — call_llm() already handles that distinction
        # internally, so this function doesn't need its own try/except.
        return FALLBACK_SQL

    match = re.search(r"```sql(.*?)```", raw, re.DOTALL)
    return (match.group(1).strip() if match else raw.strip())


@router.post("/ask")
def ask_copilot(body: CopilotRequest, db: Session = Depends(get_db)):
    try:
        sql = generate_sql(body.question)
        validated_sql = sanitize_sql(sql)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = db.execute(text(validated_sql))
        columns = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query execution failed: {e}")

    answer = synthesize_copilot_answer(body.question, validated_sql, columns, rows)

    return {
        "question": body.question,
        "sql": validated_sql,
        "columns": columns,
        "rows": rows,
        "answer": answer,
    }
