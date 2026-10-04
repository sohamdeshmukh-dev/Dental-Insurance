# Dental Benefits Optimizer

An **agentic dental benefits decision-support system** (Lincoln Financial, CodeLinc 11). It helps
an employee and their family understand what a procedure will cost, what their plan covers, which
nearby dentists are in network, when to schedule to make the best use of benefits, how to pay over
time, and what to do in an emergency.

Core principle — **LLMs interpret. Deterministic services calculate. Verified systems provide facts.**
No LLM ever invents a coinsurance %, deductible, annual maximum, network status, price, points, or
balance. Every number comes from the coverage engine or structured data; the model only narrates.

## Features

- **Ask the AI** — natural-language chat. Interprets the procedure, shows an **in-network vs
  out-of-network** cost receipt with a "Why this number?" rule breakdown. Guardrailed: PII
  redaction, prompt-injection screening, off-topic redirect, and **red-flag symptom → emergency**.
- **Dashboard** — funding available through the plan year ($2,000 annual max): gauge, month-by-month
  chart, spend-by-category, unused-benefit reminder.
- **Family / dependents** — one guardian account (Jordan Lee) + a child dependent (Riley Lee), each
  with their own $2,000 limit; a **profile switcher** and family-overview so parents can monitor a
  child's benefits.
- **Find a dentist** — Mapbox radar of verified in-network and out-of-network clinics. Clicking a
  clinic shows a **per-clinic pre-estimate** (your estimated cost for each service). Out-of-network
  clinics offer **pre-authorization** (simulated submission to Lincoln → mock decision).
- **Rewards** — prototype loyalty program tied to preventive & recommended care (tiers, points,
  gift cards, same-dentist discounts, cash/experience sweepstakes). Dependents earn too.
- **Care Plan** — multi-visit treatment tracker with payment options and **aftercare suggestions**
  (food/comfort items → Amazon category-search links; suggestions, not medical advice).
- **Payments** — build an itinerary at one clinic, choose a term, and set up a **payment plan**
  (deterministic amortization) sent to the dentist for approval → simulated active agreement.
- **Emergency / PTO** — on a red-flag symptom, surfaces urgent care and a simulated **emergency
  Paid-Time-Off** request to the employer.

> **Prototype boundaries:** rewards, sweepstakes, pre-authorizations, payment-plan "contracts", and
> PTO requests are **illustrative demos** — clearly labeled, with no real money movement, no real
> payer/HR submission, and no binding agreements.

## Architecture

**Backend — FastAPI + Pydantic** (`apps/api/`). The deterministic core:

| Piece | File |
|---|---|
| Deterministic coverage engine (modular rules, `Decimal`) | `services/coverage.py` |
| Procedure intelligence (NL → CDT, never silent) | `services/procedures.py` |
| Provider search (network status from membership only) | `services/providers.py` |
| Per-clinic pre-estimates | `services/clinic.py` |
| Annual-max tracker, funding timeline, reminders | `services/benefits.py` |
| Care sequencing (urgency > deps > eligibility > max > cost) | `services/care_planner.py` |
| Rewards engine (preventive-care loyalty) | `services/rewards.py` |
| Out-of-network pre-authorization (simulated) | `services/preauth.py` |
| Payment plans (simulated agreement) | `services/payment_plans.py` |
| Emergency PTO (simulated HR) | `services/pto.py` |
| **Guardrails** (input screening + output number-check) | `services/guardrails.py` |
| **AWS Bedrock** estimation agent (optional, tool-loop) | `services/bedrock.py` |
| Rule-based supervisor (fallback agent) | `services/supervisor.py` |
| Narrow agent tools / account | `services/tools.py` |

**Frontend — React + Vite + TypeScript + Framer Motion** (`apps/web/`). Component views for each
feature, fluid animations, in the Lincoln brand. Mapbox token from `VITE_MAPBOX_TOKEN`.

**Bedrock (optional):** the agent invokes a Bedrock model with a tool-use loop over the deterministic
services — the model narrates, numbers come only from tools, and output is checked so every $/%
matches an engine fact. Without AWS creds it falls back to the rule-based supervisor; nothing calls
AWS unless configured (see `apps/api/.env.example`).

## Run

```bash
# backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                         # 51 tests
cd apps/api && ../../.venv/bin/uvicorn main:app --reload   # :8000

# frontend
cd apps/web
cp .env.example .env.local    # add your Mapbox public token (VITE_MAPBOX_TOKEN)
npm install && npm run dev    # http://localhost:5173
```

Each view falls back to embedded demo data when the backend isn't running.

## Secrets

No secrets are committed. The Mapbox **public** token lives in gitignored `apps/web/.env.local`
(`apps/web/.env.example` is the template). AWS Bedrock credentials, if used, live in gitignored
`apps/api/.env`.
