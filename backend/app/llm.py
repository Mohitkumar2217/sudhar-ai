"""
Thin wrapper around the Groq API for every LLM touchpoint in this app:
1. Dunning email copywriting (non-punitive, friendly tone)
2. CFO Copilot — both SQL generation (routers/copilot.py) and result synthesis

Everything routes through call_llm() below. Previously, copilot.py's SQL
generation constructed its own Anthropic client and duplicated the
request/fallback logic instead of sharing this module's — that duplication is
exactly how one call site ended up with error handling and another didn't
(the bug that surfaced when the account's credit balance ran out). There's
now exactly one client, one request path, one fallback behavior.
"""
import os
import json
 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        _client = Groq(api_key=GROQ_API_KEY)
    except Exception as e: 
        print(f"[llm] Groq client unavailable, falling back to offline mode: {e}")
        _client = None


def call_llm(prompt: str, max_tokens: int = 500) -> str | None:
    """Returns the model's text response, or None if no client is configured
    or the API call fails for any reason (no credit balance, rate limit,
    network error, bad model name, etc.). Every caller in this file and in
    routers/copilot.py must treat None as "use the offline fallback" —
    nothing here ever raises out to the request handler."""
    if not _client:
        return None
    try:
        response = _client.chat.completions.create(
            model=MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[llm] Groq API call failed, falling back to offline mode: {e}")
        return None


def generate_dunning_copy(customer_name: str, product_name: str, update_link: str, days_overdue: int) -> dict:
    prompt = f"""You are a customer success copywriter. Write a short, friendly, frictionless
                 transactional billing email.
                 
                 Customer: {customer_name}
                 Product: {product_name}
                 Days overdue: {days_overdue}
                 Update link: {update_link}
                 
                 Rules:
                 - Never use words like 'collections', 'terminated', 'failed payment', or 'delinquent'.
                 - Emphasize continuity of service and a quick 1-click update.
                 - Respond with ONLY a JSON object: {{"subject": "...", "body_text": "..."}}
                 """

    raw = call_llm(prompt, max_tokens=300)
    if raw:
        try:
            cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            pass

    # Offline fallback template
    return {
        "subject": f"Quick update needed for your {product_name} subscription",
        "body_text": (
            f"Hi {customer_name}, we ran into a small hiccup renewing your subscription. "
            f"No action needed beyond a quick update here: {update_link}"
        ),
    }


def synthesize_copilot_answer(question: str, sql: str, columns: list, rows: list) -> str:
    prompt = f"""You are a CFO analyst. Answer this question using ONLY the data below —
                 never invent numbers not present in the rows.
                 
                 Question: {question}
                 SQL run: {sql}
                 Columns: {columns}
                 Rows: {rows}
                 
                 Lead with the key number(s), name the top driver if visible in the data, and give one
                 concrete recommendation. Keep it under 120 words.
                 """
                 
    raw = call_llm(prompt, max_tokens=300)
    if raw:
        return raw.strip()

    # Offline fallback: just describe the raw result set honestly.
    if not rows:
        return "No matching data was found for that query."
    return f"Query returned {len(rows)} row(s) with columns {columns}. First row: {rows[0]}"
