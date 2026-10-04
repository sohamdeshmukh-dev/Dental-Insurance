# Dental Benefits Optimizer Development Rules

Agentic dental benefits decision-support system. LLMs interpret, deterministic services calculate, verified systems provide facts.

IMPORTANT ARCHITECTURAL RULES:

1. LLMs must never calculate final insurance benefits.
2. All benefit calculations must use the deterministic coverage engine (`apps/api/services/coverage.py`).
3. Network status must come from provider network data (`provider_networks`), never Mapbox.
4. Mapbox handles mapping, geocoding, distance and directions.
5. Every plan-derived value must retain source provenance.
6. Agents interact with external systems exclusively through tools (`apps/api/services/tools.py`).
7. Never fabricate missing plan data; return NEEDS_INFORMATION instead.
8. Never expose API secrets to the frontend (no `NEXT_PUBLIC_*` secrets).
9. Clinical urgency overrides financial optimization.
10. Estimates must clearly state that actual claim processing determines final benefits.
11. Reminders must not say "you are losing $X"; say "up to approximately $X of remaining eligible plan benefits".
12. Rewards are tied to preventive/recommended care only — never reward unnecessary or delayed care.
13. Simulated workflows (rewards, sweepstakes, pre-authorization, payment-plan "contracts", PTO) must be
    clearly labeled demos: no real money movement, no real payer/HR submission, no binding agreements.
14. The AWS Bedrock agent (`services/bedrock.py`) is optional: the model narrates, numbers come only from
    tools, and output is checked against engine facts. Without AWS creds, fall back to the rule-based
    supervisor. AWS creds live in gitignored `apps/api/.env` only.
15. Guardrails (`services/guardrails.py`) run on every agent call: PII redaction, injection screening,
    off-topic redirect, and red-flag symptoms → emergency (clinical urgency before finances).
16. Per-member: endpoints take `member_id`; each member (guardian/dependent) has their own plan/usage.

Stack: FastAPI + Pydantic (backend), React + Vite + TypeScript + Framer Motion (frontend, in apps/web),
PostgreSQL + pgvector (planned; mocks are in-memory today), Mapbox GL JS, IBM watsonx Orchestrate (planned runtime).

Every new feature must include: types, error handling, loading state, tests, telemetry, source provenance where applicable.

Run tests: `cd apps/api && ../../.venv/bin/python -m pytest ../../tests -q`
Run API:   `cd apps/api && ../../.venv/bin/uvicorn main:app --reload`
Run web:   `cd apps/web && npm install && npm run dev`  (Mapbox token in apps/web/.env.local)
