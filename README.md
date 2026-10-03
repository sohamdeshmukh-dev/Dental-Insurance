# Dental Benefits Optimizer

An **agentic benefits decision-support system** for the CodeLinc 11 challenge. It answers:
*"I need this dental procedure — what will my plan cover, what might I pay, which nearby
dentists are in network, and when should I schedule to make the best use of my benefits?"*

Core principle: **LLMs interpret. Deterministic services calculate. Verified systems provide facts.**
No LLM ever invents a coinsurance %, deductible, annual maximum, network status, price, or balance.

## What's built (Phases 1–4)

A complete Python/FastAPI backend with the deterministic intelligence and the agent orchestration:

| Piece | File | Notes |
|---|---|---|
| Typed schemas | `apps/api/schemas.py` | Pydantic models, all with source provenance |
| Procedure intelligence | `apps/api/services/procedures.py` | NL → CDT; never assigns a code silently |
| **Deterministic coverage engine** | `apps/api/services/coverage.py` | Modular rule pipeline, `Decimal` math |
| Cost provider interface | `apps/api/services/cost.py` | `MockCostDataProvider`; `FairHealthProvider` gated on licensed access |
| Provider search | `apps/api/services/providers.py` | Network status from membership records **only** |
| Geo | `apps/api/services/geo.py` | Mock + Mapbox geocoder (server-side token) |
| Annual max tracker + reminders | `apps/api/services/benefits.py` | No "you are losing $X" framing |
| Care sequencing | `apps/api/services/care_planner.py` | Clinical urgency > dependencies > eligibility > max > cost |
| Agent tools | `apps/api/services/tools.py` | Narrow tools; agents never hit data directly |
| Supervisor orchestrator | `apps/api/services/supervisor.py` | UNDERSTAND→VERIFY→CALCULATE→LOCATE→OPTIMIZE→VALIDATE→EXPLAIN |
| HTTP API | `apps/api/main.py` | FastAPI routes |

The LLM-facing agents (intake, procedure, explanation) are deterministic rule-based stand-ins
so the pipeline runs offline — each is a clean seam where a **watsonx Orchestrate** agent plugs in.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                       # 22 tests
cd apps/api && ../../.venv/bin/uvicorn main:app --reload
```

## Key endpoints

- `POST /api/v1/procedures/interpret` — NL → candidate CDT codes
- `POST /api/v1/benefits/estimate` — in- vs out-of-network cost comparison
- `GET  /api/v1/providers` — verified in-network dentists near a ZIP
- `GET  /api/v1/benefits/usage` — annual maximum dashboard data
- `POST /api/v1/care-plan/optimize` — treatment sequencing
- `POST /api/v1/agent/message` — full supervisor workflow (the demo)

## Demo

```
"My dentist says I need a root canal and crown on tooth 14. I have Lincoln Dental, live near 19122."
→ Root canal D3330 (molar, confident) + Crown D2740 (needs confirmation)
→ 3 verified in-network dentists, closest 1.0 mi
→ Root canal Oct 2026 ($210 member) → Crown Jan 2027 ($575) — deferred because the
  annual maximum would cap the in-year payment; urgency still overrides this.
→ Plain-language explanation with provenance + estimate disclaimer.
```

## Not yet built (Phases 1 frontend, 5 enterprise)

Next.js/Mapbox frontend, PostgreSQL+pgvector (mocks are in-memory), plan-PDF RAG ingestion,
and live Lincoln / FAIR Health / watsonx Orchestrate integrations. See `CLAUDE.md` for the rules
any of that work must follow.
