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

Stack: FastAPI + Pydantic (backend), Next.js + TypeScript + Tailwind + shadcn/ui (frontend, planned),
PostgreSQL + pgvector (planned; mocks are in-memory today), Mapbox GL JS, IBM watsonx Orchestrate (planned runtime).

Every new feature must include: types, error handling, loading state, tests, telemetry, source provenance where applicable.

Run tests: `cd apps/api && ../../.venv/bin/python -m pytest ../../tests -q`
Run API:   `cd apps/api && ../../.venv/bin/uvicorn main:app --reload`
