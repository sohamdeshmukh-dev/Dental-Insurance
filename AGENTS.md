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

Stack: FastAPI + Pydantic (backend), React + Vite + TypeScript + Framer Motion (frontend, in apps/web),
PostgreSQL + pgvector (planned; mocks are in-memory today), Mapbox GL JS, IBM watsonx Orchestrate (planned runtime).

AWS BEDROCK AGENT (optional LLM runtime for `POST /api/v1/agent/message`):

- `apps/api/services/bedrock_agent.py` runs a Bedrock `Converse` tool-use loop. The model interprets
  and narrates; it must only reach data through the five declared tools, which map 1:1 to
  `services/tools.py`. It must never calculate a benefit value or assert network status — rules 1, 3,
  and 6 above apply unchanged. The system prompt enforces this and the model has no other data source.
- Activation is gated on the `BEDROCK_MODEL_ID` env var; unset means the deterministic supervisor runs.
  On any Bedrock runtime failure, degrade gracefully to the supervisor (never surface a raw error).
- `boto3` is imported lazily so the app and tests run without it. AWS credentials/region come from the
  environment (IAM role preferred); no AWS secret is ever exposed to the frontend (rule 8).
- Requires model access granted in the Bedrock console and `bedrock:InvokeModel` permission. App targets
  Python 3.10+.

Every new feature must include: types, error handling, loading state, tests, telemetry, source provenance where applicable.

Run tests: `cd apps/api && ../../.venv/bin/python -m pytest ../../tests -q`
Run API:   `cd apps/api && ../../.venv/bin/uvicorn main:app --reload`

<!-- BEGIN AWS Agent Toolkit rules -->
# AWS Guidance

- Where these AWS rules conflict with the project's own instructions, the
  project's instructions take precedence.
- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.

## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.
<!-- END AWS Agent Toolkit rules -->
