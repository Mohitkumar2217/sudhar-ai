"""
Thin wrapper around the Anthropic API for the two LLM touchpoints in this app:
1. Dunning email copywriting (non-punitive, friendly tone)
2. CFO Copilot synthesis (summarizing SQL results in plain English)

Both fall back to a static template if ANTHROPIC_API_KEY isn't set, so the rest
of the app is runnable and testable without any API access.
"""
import os
import json

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

_client = None
if ANTHROPIC_API_KEY:
    try:
        import anthropic
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except ImportError:
        _client = None


def _call_claude(prompt: str, max_tokens: int = 500) -> str | None:
    if not _client:
        return None
    response = _client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


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
- Respond with ONLY a JSON object: {{"subject": "...", "body_text": "..."}}"""

    raw = _call_claude(prompt, max_tokens=300)
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
concrete recommendation. Keep it under 120 words."""

    raw = _call_claude(prompt, max_tokens=300)
    if raw:
        return raw.strip()

    # Offline fallback: just describe the raw result set honestly.
    if not rows:
        return "No matching data was found for that query."
    return f"Query returned {len(rows)} row(s) with columns {columns}. First row: {rows[0]}"
