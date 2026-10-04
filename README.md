# Lincoln Dental Connect

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
.venv/bin/python -m pytest -q                       # 33 tests
cd apps/api && ../../.venv/bin/uvicorn main:app --reload
```

## Key endpoints

- `POST /api/v1/procedures/interpret` — NL → candidate CDT codes
- `POST /api/v1/benefits/estimate` — in- vs out-of-network cost comparison
- `GET  /api/v1/providers` — verified in-network dentists near a ZIP
- `GET  /api/v1/benefits/usage` — annual maximum dashboard data
- `POST /api/v1/care-plan/optimize` — treatment sequencing
- `POST /api/v1/agent/message` — full agent workflow (the demo; deterministic supervisor by default,
  or the AWS Bedrock orchestrator when `BEDROCK_MODEL_ID` is set — see below)

## Demo

```
"My dentist says I need a root canal and crown on tooth 14. I have Lincoln Dental, live near 19122."
→ Root canal D3330 (molar, confident) + Crown D2740 (needs confirmation)
→ 3 verified in-network dentists, closest 1.0 mi
→ Root canal Oct 2026 ($210 member) → Crown Jan 2027 ($575) — deferred because the
  annual maximum would cap the in-year payment; urgency still overrides this.
→ Plain-language explanation with provenance + estimate disclaimer.
```

## AWS Bedrock agent (optional)

`POST /api/v1/agent/message` can run on an **AWS Bedrock** large-language model instead of the
deterministic rule-based supervisor. It is **opt-in** and **additive** — with no configuration,
the endpoint behaves exactly as before.

**What it does.** A Bedrock `Converse` *tool-use* loop lets the model INTERPRET the member's
request and NARRATE the answer, while every fact comes from the deterministic engine. The model
is given five tools that map 1:1 to `services/tools.py` and nothing else — so it cannot invent a
coinsurance %, price, member cost, network status, or benefit balance; it can only decide *which*
tool to call and explain the verified result it is handed:

| Tool the model may call | Deterministic function it runs |
|---|---|
| `interpret_procedure` | `procedures.interpret` — NL → candidate CDT codes (keeps `requires_confirmation`) |
| `compare_networks` | `coverage.calculate_coverage` — in- vs out-of-network cost |
| `search_network_providers` | `providers.search_providers` — nearby offices; `VERIFIED_IN_NETWORK` only via membership records |
| `get_benefit_usage` | `benefits.get_benefit_usage` — annual-maximum usage |
| `optimize_treatment_sequence` | `care_planner` — treatment ordering |

The loop is bounded (`MAX_TURNS`), each model turn and tool call is traced, and if the Bedrock
call fails at runtime the endpoint **falls back** to the deterministic supervisor and tags the
response with `engine: "supervisor"` and a `bedrock_error` note. Code lives in
`apps/api/services/bedrock_agent.py`. `boto3` is imported lazily, so the app and the 33-test
suite run with no AWS dependency installed.

### What you need from your AWS account

Live calls require all of the following; until they are in place the endpoint simply uses the
deterministic supervisor.

1. **A Bedrock-enabled AWS account**, and **model access granted** for the specific model you
   intend to use (e.g. an Anthropic Claude or Amazon Nova model). Model access is a one-time
   manual opt-in per model, per region, in the Bedrock console under *Model access*.
2. **An IAM identity** (role or user) with permission to invoke the model — at minimum
   `bedrock:InvokeModel` on that model's ARN. Prefer an IAM role over long-lived keys; never put
   secrets in the frontend.
3. **The model id** for the model you were granted — this becomes `BEDROCK_MODEL_ID`.
4. **A region** where you have model access — e.g. `us-east-1`.

### Enabling it

```bash
.venv/bin/pip install -r requirements.txt      # installs boto3

export BEDROCK_MODEL_ID="anthropic.claude-3-5-sonnet-20241022-v2:0"   # the model you were granted
export AWS_REGION="us-east-1"                                          # a region with model access
# plus standard AWS credentials in the environment (IAM role, AWS_PROFILE,
# or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY). boto3 resolves these automatically.

cd apps/api && ../../.venv/bin/uvicorn main:app --reload
```

### Background research briefs (Bedrock only)

After a chat reply that prices a procedure, the page calls `POST /api/v1/research/{session_id}/run`;
the agent researches it in that request and the page shows a banner when `GET /api/v1/research/{session_id}`
returns `READY`. Briefs live in memory by default (fine locally). On serverless (Vercel) set `BRIEFS_TABLE`
to a DynamoDB table so every instance sees the same briefs:

```bash
aws cloudformation deploy --template-file infra/briefs-table.yaml \
  --stack-name dental-research-briefs --capabilities CAPABILITY_IAM
# attach the PolicyArn stack output to the IAM user/role the app runs as, then:
export BRIEFS_TABLE=dental-research-briefs
```

With `BEDROCK_MODEL_ID` set, `POST /api/v1/agent/message` runs on Bedrock (responses carry
`engine: "bedrock"`); unset, it runs the supervisor. **Note:** this app targets **Python 3.10+**.

## Not yet built (Phases 1 frontend, 5 enterprise)

Next.js/Mapbox frontend, PostgreSQL+pgvector (mocks are in-memory), plan-PDF RAG ingestion,
and live Lincoln / FAIR Health / watsonx Orchestrate integrations. See `CLAUDE.md` for the rules
any of that work must follow.
