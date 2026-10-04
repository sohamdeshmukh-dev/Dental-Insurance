# Lincoln Dental Connect

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
- `POST /api/v1/procedures/interpret` — NL → candidate CDT codes
- `POST /api/v1/benefits/estimate` — in- vs out-of-network cost comparison
- `GET  /api/v1/providers` — verified in-network dentists near a ZIP
- `GET  /api/v1/benefits/usage` — annual maximum dashboard data
- `POST /api/v1/care-plan/optimize` — treatment sequencing
- `POST /api/v1/agent/message` — full agent workflow (the demo; deterministic supervisor by default,
  or the AWS Bedrock orchestrator when `BEDROCK_MODEL_ID` is set — see below)

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
| **AWS Bedrock** estimation agent (optional, tool-loop) | `services/bedrock_agent.py` |
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

## Secrets

No secrets are committed. The Mapbox **public** token lives in gitignored `apps/web/.env.local`
(`apps/web/.env.example` is the template). AWS Bedrock credentials, if used, live in gitignored
`apps/api/.env`.
