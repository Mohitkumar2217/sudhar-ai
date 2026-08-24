# Sudhar AI

**सुधार — "correction / improvement."** An autonomous revenue-recovery engine for B2B
SaaS: it detects failed payments, figures out *why* they failed, decides the right
recovery action (silent retry vs. dunning email vs. escalation), executes it, and
answers plain-English finance questions through a guarded AI "CFO Copilot."

This README documents what was actually built and why, step by step, so it doubles
as both a run guide and an implementation writeup.

---

## 1. The problem this solves

SaaS companies lose recurring revenue silently: a card expires, a charge is declined
for insufficient funds, a webhook fails — and by default nobody notices until a
customer's subscription has already lapsed. Sudhar AI treats every failed payment as
a workflow to be triaged and worked automatically, instead of a support ticket
someone has to notice.

## 2. Design philosophy: right-sized, not maximal

The original architecture draft for this project specified a "hyperscale" stack —
Temporal.io, Kafka, ClickHouse, Redis distributed locks, a trained LightGBM retry
model. All defensible choices *at scale*, all wrong for a first build with zero
production traffic and zero training data. Every design decision below was made by
asking: **does this component solve a problem I actually have yet?**

| Concern | Full/production version | What was actually built | Why |
|---|---|---|---|
| Workflow durability | Temporal.io / Kafka | A plain Postgres `status` column + `next_action_scheduled_at` timestamp, advanced by an idempotent `process_due_invoices()` call | A workflow engine solves crash-recovery and horizontal scale — problems that don't exist with one process and a database. The state machine transitions are identical either way. |
| Idempotency | Redis distributed locks | A unique constraint on `(tenant_id, invoice_id)` | Same guarantee — a duplicate insert just fails — with one fewer moving part. |
| Retry timing | Trained LightGBM model | A small heuristic table (`retry_rules.py`) | There's no historical data to train on yet. A model "trained" on synthetic data would look sophisticated but encode nothing real — a transparent heuristic is more honest and easier to defend. |
| Analytics store | ClickHouse | Postgres/SQLite | Not enough row volume yet to need a columnar OLAP engine. |
| Card-update flow | JWT magic-link portal | Left as a documented next step | High visual payoff but not load-bearing for proving the core loop works. |

What was **kept intact** from the original spec because it was already right-sized:
the ISO 8583 decline-code taxonomy, the card-network compliance guardrails (never
retry hard declines; cap at 4 attempts / 14 days — real rules that carry real fines
if violated), and the rule that the LLM in the CFO Copilot is only ever allowed to
*summarize* numbers that came back from an executed, sanitized SQL query — never
invent them.

---

## 3. Build order and what each step does

### Step 1 — Data model (`schema.sql`, `app/models.py`, `app/db.py`)
Four tables: `tenants` (the SaaS companies using Sudhar AI), `customers` (their
end-users), `failed_invoices` (the core work item, one row per failed payment, with
a `status` enum acting as the state machine), and `recovery_actions` (an audit log
of every retry/email sent). `schema.sql` is the real Postgres DDL for deployment;
`db.py` wires SQLAlchemy to run against local SQLite by default so the whole project
is runnable with zero infrastructure, and against Postgres the moment you set
`DATABASE_URL`. This split — reference DDL for production, ORM models for
day-to-day dev — means you never write the schema twice.

### Step 2 — Deterministic root-cause classification (`app/decline_taxonomy.py`)
A lookup table mapping raw gateway decline codes (`insufficient_funds`,
`expired_card`, `stolen_card`, ...) to their ISO 8583 numeric code and a failure
domain: `HARD_DECLINE`, `SOFT_DECLINE`, `TECHNICAL_FAILURE`, or `DISPUTED_CHURN`.
This stays rule-based deliberately — it's a small, auditable table, not a place an
ML model or LLM adds value. The one piece of real logic on top: if a customer has
been inactive for under 3 days *and* has a low health score, the failure is
reclassified as likely voluntary churn rather than a fixable payment problem, which
lowers the expected recovery rate and changes downstream handling.

### Step 3 — Retry timing and compliance guardrails (`app/retry_rules.py`)
Two responsibilities: (a) a backoff table saying how long to wait before each retry
attempt (24h → 72h → 120h, roughly aligned with typical issuer settlement windows),
and (b) `is_retry_permissible()`, which enforces the two hard rules that actually
matter operationally — never retry a hard-declined card (ISO codes 04/14/41/43/54),
and never exceed 4 attempts or a 14-day window. Card networks fine merchants for
violating these, so this function is the one piece of "boring" logic that's worth
being strict about even in an MVP.

### Step 4 — The recovery engine (`app/recovery_engine.py`)
This is the actual product logic, expressed as one idempotent function,
`process_due_invoices()`, instead of a long-running workflow:
1. Every `PENDING` invoice gets classified (Step 2) and routed to either
   `SCHEDULED_RETRY` or `DUNNING_ACTIVE`.
2. Every invoice in `DUNNING_ACTIVE` that hasn't been emailed yet gets a
   personalized dunning email generated and sent.
3. Every invoice in `SCHEDULED_RETRY` whose scheduled time has arrived gets a
   (simulated) retry attempt — checked against the compliance guardrails first —
   and moves to `RECOVERED`, back to `SCHEDULED_RETRY` with an incremented attempt
   count, or escalates to dunning after attempt 3.

Calling this function repeatedly is safe — each invoice only acts once per
eligible state — which is what makes a cron job (or a manual "run cycle" button)
an adequate substitute for a workflow engine at this scale.

### Step 5 — LLM integration (`app/llm.py`)
One thin wrapper around the Anthropic API used in exactly two places: writing
non-punitive dunning email copy, and summarizing SQL results for the CFO Copilot.
Both functions check for `ANTHROPIC_API_KEY` and fall back to a static template if
it's missing, so the rest of the app — and anyone reviewing this code — can run and
test it without needing an API key.

### Step 6 — Email delivery (`app/email_sender.py`)
Sends through Resend's API if `RESEND_API_KEY` is set; otherwise logs the email to
the console. Same pattern as Step 5: the integration is real, but nothing about the
rest of the system depends on it being configured.

### Step 7 — Seed data (`app/seed.py`)
Generates ~60 fake customers and ~200 fake failed invoices with a realistic
distribution of decline codes (insufficient funds and expired cards dominate, lost/
stolen cards are rare — matching real-world frequency) so the system is demoable
immediately without wiring a real Stripe webhook integration.

### Step 8 — API layer (`app/routers/`)
Three route groups:
- **`invoices.py`** — list invoices (filterable by status), and
  `POST /invoices/run-recovery-cycle`, the manual trigger for Step 4's engine
  (a cron job in production).
- **`dashboard.py`** — one aggregation endpoint: revenue at risk, revenue
  recovered, recovery rate, top failure reasons, and the most recent actions taken.
  All computed with plain SQL aggregates — no caching layer needed yet.
- **`copilot.py`** — the CFO Copilot. Takes a natural-language question, asks
  Claude to generate a SQL `SELECT` against a fixed schema description, runs it
  through `sanitize_sql()` (blocks any mutation keyword and anything that isn't a
  `SELECT`), executes it, and asks Claude to summarize *only* the returned rows.
  This is the project's strongest feature because the guardrail is simple but the
  result feels intelligent: the model never gets to assert a number that isn't
  backed by an actual query result.

### Step 9 — Wiring (`app/main.py`)
Creates tables on startup, mounts the routers, enables permissive CORS for local
frontend development (tighten before any real deployment).

### Step 10 — Real Stripe webhook ingestion (`app/routers/webhooks.py`, `app/stripe_signature.py`)
Replaces the seed script as the real path for getting failed-payment events into
the system. `POST /webhooks/stripe/{tenant_id}` does three things a webhook
receiver has to get right:

1. **Verifies the signature for real.** `stripe_signature.py` implements Stripe's
   actual `Stripe-Signature: t=<timestamp>,v1=<hmac>` scheme — HMAC-SHA256 over
   `"{timestamp}.{raw_body}"`, checked with `hmac.compare_digest` (constant-time,
   so it isn't vulnerable to timing attacks), plus a 5-minute tolerance window to
   reject replayed payloads. A bad or missing signature returns `401` before
   anything touches the database.
2. **Handles idempotency at the event level**, not just the invoice level. Stripe
   redelivers a webhook on any non-2xx response, so a repeat `event_id` is normal
   traffic, not an error — it's checked against a `webhook_events` table and
   short-circuited to `{"status": "ignored"}` before any processing happens. The
   existing `(tenant_id, invoice_id)` unique constraint is kept as a second,
   independent safety net.
3. **Auto-creates the customer record** on first sight, since Stripe's payload
   doesn't carry the engagement signals (`health_score`, `days_active_past_30d`)
   the classifier uses — those get backfilled from a separate telemetry source
   (Segment/Mixpanel/etc.) in a real deployment, and default to neutral values here.

Because this sandbox can't reach `stripe.com` directly, correctness was proven with
`scripts/send_test_webhook.py` — not a mock of the endpoint, but a real HTTP
request carrying a correctly HMAC-signed payload built the same way Stripe builds
one, hitting the exact same verification code a production deployment would run.

### Step 11 — Magic-link portal (`app/magic_link.py`, `app/routers/portal.py`, `frontend/app/update/`)
The "update your payment method" flow referenced in the dunning email, now real
instead of a placeholder URL string.

- **`magic_link.py`** generates a JWT (`tenant_id`, `customer_id`, `invoice_id`,
  15-minute `exp`) signed with `MAGIC_LINK_SECRET`. The token *is* the
  authentication — no login, no password — which is standard for this kind of
  single-purpose billing link, and is why the expiry is short and the scope is
  narrowed to exactly one invoice.
- **`recovery_engine.py`** was updated to call `generate_magic_link()` instead of
  building a fake URL, so every dunning email sent by Step 4 now carries a real,
  independently verifiable link.
- **`routers/portal.py`** exposes `GET /portal/invoice?token=...` (returns invoice
  + customer + tenant details, or `already_recovered: true` if it's already been
  handled) and `POST /portal/update-card` (marks the invoice `RECOVERED` and logs
  a `CARD_UPDATED` action). Both decode and verify the JWT before touching the
  database; an expired or tampered token gets a `401` with a generic "invalid or
  expired" message — expired and tampered aren't distinguished in the response,
  so a bad actor probing tokens can't tell which case they hit.
- **PCI scope, kept honest.** This endpoint never receives raw card data, and the
  "update card" action doesn't pretend to collect any — it's a confirmation step.
  A real deployment embeds a gateway-hosted card form (Stripe's Payment Element or
  equivalent) that tokenizes the card entirely client-side, so this backend only
  ever sees a gateway token. Building a fake card form that *looked* like it
  collected real card details would misrepresent what the code does, so it was
  left out rather than faked.
- **`frontend/app/update/`** is the page itself — a single-question layout
  (styled to match the reference screenshot even more closely than the dashboard,
  since it's the same "one question, one action" shape) with four states: loading,
  invalid/expired link, already handled, and success.

Verified against real tokens generated by a live recovery cycle, not synthetic
ones: fetched the invoice for a valid token, confirmed the update, re-fetched the
same token and confirmed it correctly reported `already_recovered: true`, and
confirmed a garbage token is rejected with `401`. The frontend's exact fetch
request (including the `Origin` header a browser would send) was replayed against
the running backend to confirm the response shape matches what the page expects,
and `npm run build` compiled the new route cleanly.

### Step 12 — Synthetic-data retry-timing model (`app/synthetic_retry_data.py`, `scripts/train_retry_model.py`, `app/retry_model.py`)
An actual trained model swapped in behind a flag, per the roadmap discussion — but
built on **synthetic labels**, since real retry-outcome data doesn't exist yet (see
below) and doesn't exist publicly anywhere either. Every synthetic assumption is a
named constant in `synthetic_retry_data.py` specifically so it's easy to find,
question, and delete once real data exists.

- **`synthetic_retry_data.py`** generates labeled training rows by running
  `decline_taxonomy.py`'s existing base recovery rates through three invented
  timing effects (morning retries +15%, "payday window" retries +20%, each
  attempt after the first ×0.85) plus random noise, then samples a `recovered`
  0/1 outcome. Hard declines and churn-suspects are excluded — `retry_rules.py`
  already forbids retrying those, so there's nothing timing-related to learn.
- **`scripts/train_retry_model.py`** trains a `HistGradientBoostingClassifier`
  (scikit-learn's built-in gradient boosting — same algorithm family as the
  LightGBM the original spec called for, without adding a new dependency) on an
  80/20 stratified split, evaluates with AUC/accuracy/classification report, and
  saves both the model and a metadata JSON. That metadata always includes
  `"is_synthetic": true` and a warning string, so the flag travels with the
  artifact rather than living only in a comment.
- **`retry_model.py`** loads the artifact once and exposes
  `predict_best_retry_delay_hours()`, which scores 7 candidate delays (24h-168h)
  and returns the best. `recovery_engine.py` calls this INSTEAD of the
  `retry_rules.py` heuristic only when `RETRY_MODEL_ENABLED=true` — any load or
  prediction failure falls back to the heuristic automatically, so the recovery
  loop never depends on the model artifact existing.

**What running it actually showed**, not just what it's supposed to do: test AUC
came out to 0.71 (meaningfully above random, well below suspiciously perfect —
consistent with the deliberate noise added during generation). But probing *why*
the model recommended a 7-day delay for a sample invoice showed it had precisely
located the invented `PAYDAY_BOOST` effect (probability jumping from 0.68 to 0.77
right at the assumed payday window) — a clean demonstration that **the model can't
be smarter than the assumptions baked into its training labels**. That's not a
bug in the code; it's the actual reason the roadmap said to hold off on this
until real data exists, made concrete instead of theoretical.

**To retrain on real data once it exists:** replace the
`generate_synthetic_dataset()` call in `train_retry_model.py` with a query
joining `RecoveryAction` to `FailedInvoice` (real outcome, at what attempt count
and what real timestamp), keep the same feature columns, and flip `is_synthetic`
to `False` in the saved metadata.

---

## 4. Quickstart

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional — the app runs with no keys set

python -m app.seed            # generates fake tenants/customers/invoices
python -m scripts.train_retry_model   # optional — trains the synthetic retry-timing model (Step 12)
uvicorn app.main:app --reload --port 8000
```

Then:

| Endpoint | What it does |
|---|---|
| `GET /` | Health check |
| `GET /invoices?status=DUNNING_ACTIVE` | List failed invoices, optionally filtered |
| `POST /invoices/run-recovery-cycle` | Advance every invoice due for action — call repeatedly to watch the state machine progress |
| `GET /dashboard/summary` | Revenue at risk / recovered, recovery rate, top failure reasons |
| `POST /copilot/ask` | `{"question": "..."}` → guarded text-to-SQL + AI summary |
| `POST /webhooks/stripe/{tenant_id}` | Real Stripe webhook receiver (HMAC-verified) — see Section 5 to test it locally |
| `GET /portal/invoice?token=...` | Resolves a magic-link token to invoice details |
| `POST /portal/update-card` | Confirms the (simulated) card update, marks the invoice recovered |

No keys required to run the full loop end to end. Set `ANTHROPIC_API_KEY` to get
real AI-generated dunning copy and real natural-language copilot answers instead of
the static fallbacks; set `RESEND_API_KEY` to actually send the emails instead of
logging them.

## 5. Testing the webhook path

```bash
# with the server already running (see Quickstart above)
python -m scripts.send_test_webhook <tenant_id> insufficient_funds
```

This was verified against four cases, each hitting real code paths (not stubs) —
sending an actually HMAC-signed HTTP request, the same way Stripe would, since this
build environment can't reach `stripe.com` directly:

| Case | Result |
|---|---|
| Valid signature, known tenant | `200`, invoice created (`status: enqueued`) |
| Unknown `tenant_id` | `404` |
| Corrupted signature | `401 Signature mismatch` |
| Same `event_id` sent twice (simulated Stripe redelivery) | First: `200 enqueued`. Second: `200 ignored, reason: duplicate_event` |

A `stolen_card` event sent through the webhook was then confirmed to flow correctly
into the existing recovery engine: classified as `HARD_DECLINE` and routed to
`DUNNING_ACTIVE` on the next recovery cycle, exactly like a seeded invoice with the
same decline code — proving the webhook path and the recovery engine are actually
wired together, not two disconnected pieces.

## 6. Repo layout

```
backend/
  schema.sql                Postgres DDL for real deployment
  requirements.txt
  .env.example
  app/
    db.py                   SQLAlchemy engine — SQLite by default, Postgres via DATABASE_URL
    models.py               ORM models (Tenant, Customer, FailedInvoice, RecoveryAction)
    webhook_models.py       WebhookEvent — idempotency tracking for Step 10
    decline_taxonomy.py     Step 2 — deterministic classification
    retry_rules.py          Step 3 — retry timing + compliance guardrails
    recovery_engine.py      Step 4 — the core classify -> decide -> act loop
    llm.py                  Step 5 — Anthropic wrapper (dunning copy + copilot synthesis)
    email_sender.py         Step 6 — Resend integration
    seed.py                 Step 7 — fake data generator
    stripe_signature.py     Step 10 — HMAC verification (and signing, for tests)
    magic_link.py           Step 11 — signed 15-minute portal links
    synthetic_retry_data.py Step 12 — labeled synthetic training data generator
    retry_model.py          Step 12 — loads the trained model, predicts retry timing
    ml_artifacts/            Step 12 — retry_model.joblib + retry_model_meta.json (generated, not hand-written)
    main.py                 Step 9 — FastAPI app wiring
    routers/
      invoices.py           Step 8
      dashboard.py           Step 8
      copilot.py             Step 8 — the AI CFO Copilot
      webhooks.py            Step 10 — real Stripe webhook ingestion
      portal.py               Step 11 — magic-link portal API
  scripts/
    send_test_webhook.py    Sends a real signed webhook for local testing
    train_retry_model.py    Step 12 — trains and saves the retry-timing model
```

## 7. Verified working (already tested)

Seeded 60 customers / 200 invoices → ran a recovery cycle (63 invoices correctly
routed to dunning, rest scheduled for retry) → dashboard summary aggregated revenue
at risk and top failure reasons correctly → copilot endpoint generated and executed
SQL and returned a summarized answer, all in offline fallback mode with zero API
keys configured. The Stripe webhook path was independently verified end to end
(see Section 5), including a webhook-sourced invoice flowing correctly through the
existing recovery engine. The magic-link portal (Section 3, Step 11) was verified
against real tokens generated by a live recovery cycle — fetch, confirm, re-fetch
showing `already_recovered`, and a rejected garbage token — plus a clean
`npm run build` for the new `/update` route. The synthetic retry model (Section
3, Step 12) was trained and evaluated (AUC 0.71), confirmed to change actual
scheduling behavior when `RETRY_MODEL_ENABLED=true` vs. the heuristic when
`false`, and confirmed to fall back to the heuristic cleanly.

## 8. The dashboard (`frontend/`)

A Next.js 14 (App Router) console that consumes the FastAPI backend directly from
the browser — no server-side proxy, since this is a single-tenant internal tool.

**Design approach.** This is an operations console, not a marketing page, so the
visual language is data-dense and financial rather than promotional: a graphite
base with exactly two semantic accents — amber-gold for "recovered/correction" and
rust for "at risk" — plus Space Grotesk (headers), Inter (body), and IBM Plex Mono
(every number and table cell, so money reads as data). The one deliberate signature
element is the **healing pulse line** under the Recovered metric: an SVG heartbeat
trace that starts jagged on the left and settles into a steady rhythm on the right,
animating in on load. It's a literal image of *sudhar* — correction — turning
erratic failed payments into a steady, recovered signal.

**What was built, step by step:**

1. **`lib/api.ts`** — a typed fetch wrapper for the four backend endpoints
   (`getSummary`, `getInvoices`, `runRecoveryCycle`, `askCopilot`), plus a
   `formatCents` helper so currency formatting only lives in one place.
2. **`components/PulseLine.tsx`** — the signature SVG element described above,
   pure presentation, no data dependency.
3. **`components/MetricCard.tsx`** — the reusable summary-stat card (used for
   revenue at risk / recovered / recovery rate), with a `tone` prop that maps to
   the gold/rust accent system.
4. **`components/StatusPill.tsx`** — maps each `failed_invoices.status` value to a
   human label and color, so the same status vocabulary is used consistently
   everywhere the frontend touches it.
5. **`components/InvoiceTable.tsx`** — the scrollable invoice list, with a
   real empty state (not just a blank table) telling you to run the seed script.
6. **`components/CopilotPanel.tsx`** — the CFO Copilot UI: an input box, three
   suggested starter questions, an answer feed, and a collapsible `<details>` panel
   showing the exact SQL that was run — kept collapsed by default since the
   plain-English answer is the primary interface, but the SQL is always one click
   away for anyone who wants to audit it.
7. **`app/page.tsx`** — the page itself: fetches summary + invoices on load,
   exposes the "Run recovery cycle" button (calls the same endpoint you'd otherwise
   trigger from a cron job), and lays out the metric row, failure-reason strip,
   invoice table, and copilot panel.

**Verified working:** built with `npm run build` (clean TypeScript compile, no
errors), then run live with `npm run dev` against a freshly seeded backend —
confirmed the page renders with the correct title/metadata, the recovery-cycle
button correctly triggers `/invoices/run-recovery-cycle`, and the backend's CORS
headers (`access-control-allow-origin: *`) allow the browser to call
`/copilot/ask` directly.

### Running the dashboard

```bash
cd frontend
npm install
cp .env.local.example .env.local   # points at localhost:8000 by default
npm run dev
```

Make sure the backend (Section 4) is running first — the dashboard has no data of
its own.

**Note on `npm audit`:** this pins Next.js 14.2.35, the latest patched release on
the 14.x line. `npm audit` will still flag advisories that only have fixes on the
Next 16 line, which is a breaking-change upgrade out of scope for this MVP; since
this runs locally against your own backend rather than being self-hosted publicly,
that's an acceptable tradeoff for now — revisit before any real deployment.

## 9. Natural next steps, in priority order

1. ~~Replace the seed script with a real Stripe test-mode webhook listener.~~ **Done** — see Section 3, Step 10 and Section 5.
2. ~~Add the JWT magic-link "update your card" portal.~~ **Done** — see Section 3, Step 11.
3. ~~Build the retry-timing model.~~ **Done, but on synthetic data** — see Section
   3, Step 12. `RETRY_MODEL_ENABLED` stays `false` by default. Flip it to `true`
   only once `RecoveryAction` rows from real usage exist and the model has been
   retrained on them (see Step 12's retraining note) — enabling it on the
   synthetic model in production would mean trusting invented timing
   assumptions with real customer emails.
4. Before any public deployment: tighten CORS in `main.py`, replace
   `STRIPE_WEBHOOK_SECRET` and `MAGIC_LINK_SECRET`'s local-dev defaults with real
   secrets, and plan the Next 16 upgrade to clear the remaining `npm audit`
   advisories.
