"""AWS Bedrock Converse tool-use orchestrator — an OPTIONAL, additive alternative to the
rule-based ``supervisor.run()``.

Design contract (see CLAUDE.md): the model INTERPRETS and NARRATES; it never calculates a
benefit number, price, network status, or balance. Every fact comes back from the
deterministic services in ``services.tools``; the model may only decide *which* tool to call
and explain the results it is handed.

The Bedrock SDK (boto3) is imported lazily so the rest of the app — and the test suite — run
with no AWS dependency installed. ``bedrock_enabled()`` gates activation on the
``BEDROCK_MODEL_ID`` environment variable, so ``POST /api/v1/agent/message`` transparently
falls back to ``supervisor.run()`` when Bedrock is not configured.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any, Callable, Optional

from services import tools
from services.guardrails import check_output, collect_facts
from services.coverage import CALC_VERSION, in_network_savings
from services.tracing import Tracer

# Max model<->tool round trips before we stop, so a misbehaving loop can't run unbounded.
MAX_TURNS = 8

SYSTEM_PROMPT = (
    "You are the orchestration agent for a dental benefits decision-support system. "
    "Your job is to INTERPRET the member's request and NARRATE verified results in plain language. "
    "You MUST NOT invent, estimate, or calculate any coinsurance percentage, deductible, annual "
    "maximum, price, member cost, plan payment, network status, provider, or benefit balance. "
    "Every such fact must come from a tool result. When you need a fact, call the appropriate tool. "
    "To find dentist offices, call search_network_providers — never state that an office is "
    "in-network unless a tool result marks it VERIFIED_IN_NETWORK. "
    "If you cannot identify a procedure or lack required information, say so and ask for it rather "
    "than guessing. "
    "You can also compare in-network vs out-of-network cost for chosen services (compare_services), "
    "draft a simulated payment plan and send it to the dentist (create_payment_plan then "
    "send_payment_plan_to_dentist), and submit a simulated out-of-network pre-authorization to Lincoln "
    "Financial (create_preauth). These are clearly-labeled demos: no real money moves and no real payer "
    "or dentist is contacted. Confirm the member's intent before creating or sending anything, and tell "
    "them it is a simulated action. "
    "Always end with a reminder that estimates are not final and that actual "
    "benefits are determined when the claim is processed."
)


def bedrock_enabled() -> bool:
    """True when a Bedrock model is configured via the environment."""
    return bool(os.environ.get("BEDROCK_MODEL_ID"))


# ---------------------------------------------------------------------------
# Tool declarations exposed to the model. Input schemas mirror services.tools
# signatures. These are the ONLY ways the model can reach data.
# ---------------------------------------------------------------------------
def _tool_config() -> dict:
    return {
        "tools": [
            {"toolSpec": {
                "name": "interpret_procedure",
                "description": "Map a natural-language dental complaint or treatment description to "
                               "candidate CDT procedure codes. Returns matches with a confidence and a "
                               "requires_confirmation flag; a code is NEVER assigned silently.",
                "inputSchema": {"json": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "The member's description of the dental work."},
                        "tooth": {"type": "integer", "description": "Tooth number if known (helps pick a root-canal code)."},
                    },
                    "required": ["text"],
                }},
            }},
            {"toolSpec": {
                "name": "compare_networks",
                "description": "Deterministically calculate in-network vs out-of-network coverage for one "
                               "CDT code: coinsurance, deductible applied, plan payment, member payment, and "
                               "whether the annual maximum capped the payment. Also returns "
                               "annual_max_remaining_after (annual maximum left after this procedure) and "
                               "in_network_savings (member cost difference, out minus in). All numbers come "
                               "from the coverage engine with source provenance.",
                "inputSchema": {"json": {
                    "type": "object",
                    "properties": {"code": {"type": "string", "description": "CDT procedure code, e.g. D3330."}},
                    "required": ["code"],
                }},
            }},
            {"toolSpec": {
                "name": "search_network_providers",
                "description": "Find dentist offices near a ZIP code. network_status is VERIFIED_IN_NETWORK "
                               "only when backed by a provider-network membership record; otherwise "
                               "OUT_OF_NETWORK. Results are sorted by distance.",
                "inputSchema": {"json": {
                    "type": "object",
                    "properties": {
                        "zip_code": {"type": "string"},
                        "radius": {"type": "number", "description": "Search radius in miles (default 10)."},
                        "procedure": {"type": "string", "description": "CDT code the office must offer (optional)."},
                        "specialty": {"type": "string", "description": "e.g. 'Endodontist' (optional)."},
                        "include_out_of_network": {"type": "boolean"},
                    },
                    "required": ["zip_code"],
                }},
            }},
            {"toolSpec": {
                "name": "get_benefit_usage",
                "description": "Current annual-maximum usage: amount used, pending, remaining, percent used, "
                               "and remaining deductible. Deterministic, from paid-claim records.",
                "inputSchema": {"json": {"type": "object", "properties": {}}},
            }},
            {"toolSpec": {
                "name": "optimize_treatment_sequence",
                "description": "Produce a recommended ordering/timing for a set of CDT codes, honoring clinical "
                               "urgency first, then prerequisites, eligibility, annual maximum, and cost.",
                "inputSchema": {"json": {
                    "type": "object",
                    "properties": {
                        "codes": {"type": "array", "items": {"type": "string"}, "description": "CDT codes to sequence."},
                        "urgent_codes": {"type": "array", "items": {"type": "string"},
                                         "description": "Subset of codes that are clinically urgent."},
                        "network": {"type": "string", "enum": ["in", "out"]},
                    },
                    "required": ["codes"],
                }},
            }},
            {"toolSpec": {
                "name": "compare_services",
                "description": "Side-by-side in-network vs out-of-network member cost for a chosen set of CDT codes, "
                               "per service and totaled, with the savings from staying in-network. From the "
                               "coverage engine.",
                "inputSchema": {"json": {
                    "type": "object",
                    "properties": {"codes": {"type": "array", "items": {"type": "string"}}},
                    "required": ["codes"],
                }},
            }},
            {"toolSpec": {
                "name": "get_clinic_estimate",
                "description": "Estimated member cost for the services a specific clinic offers, at that clinic's "
                               "verified network status. From the coverage engine.",
                "inputSchema": {"json": {
                    "type": "object",
                    "properties": {"provider_id": {"type": "string"}},
                    "required": ["provider_id"],
                }},
            }},
            {"toolSpec": {
                "name": "create_payment_plan",
                "description": "Draft a SIMULATED payment plan for the member's estimated responsibility at a clinic "
                               "for the given CDT codes. Returns the draft with total, monthly amount, and schedule. "
                               "A draft only — it is not sent until send_payment_plan_to_dentist is called.",
                "inputSchema": {"json": {
                    "type": "object",
                    "properties": {
                        "provider_id": {"type": "string"},
                        "codes": {"type": "array", "items": {"type": "string"}},
                        "term_months": {"type": "integer", "description": "1-60; default 12."},
                    },
                    "required": ["provider_id", "codes"],
                }},
            }},
            {"toolSpec": {
                "name": "send_payment_plan_to_dentist",
                "description": "Send a drafted payment plan to the dentist for SIMULATED approval (demo; no real "
                               "contract). Use the plan_id returned by create_payment_plan.",
                "inputSchema": {"json": {
                    "type": "object",
                    "properties": {"plan_id": {"type": "string"}},
                    "required": ["plan_id"],
                }},
            }},
            {"toolSpec": {
                "name": "create_preauth",
                "description": "Submit a SIMULATED out-of-network pre-authorization form to Lincoln Financial for one "
                               "CDT code. The estimated and requested amounts come from the coverage engine, not you. "
                               "Demo only; no real payer is contacted.",
                "inputSchema": {"json": {
                    "type": "object",
                    "properties": {
                        "provider_id": {"type": "string"},
                        "code": {"type": "string"},
                        "urgency": {"type": "string", "enum": ["routine", "soon", "urgent"]},
                        "reason": {"type": "string"},
                    },
                    "required": ["provider_id", "code"],
                }},
            }},
        ]
    }


# ---------------------------------------------------------------------------
# Dispatch: map a model tool call to the deterministic implementation. This is
# the ONLY place model-chosen tool names are executed.
# ---------------------------------------------------------------------------
def _dispatch(name: str, args: dict, *, plan, member, today: date) -> Any:
    if name == "interpret_procedure":
        from services.procedures import interpret
        matches = interpret(args["text"], args.get("tooth"))
        return {"matches": [m.model_dump() for m in matches]}

    if name == "compare_networks":
        code = args["code"]
        in_net = tools.calculate_coverage(plan, member, code, "in", today)
        out_net = tools.calculate_coverage(plan, member, code, "out", today)
        return {
            "code": code,
            "in_network": in_net.model_dump(),
            "out_of_network": out_net.model_dump(),
            "in_network_savings": in_network_savings(in_net, out_net),
        }

    if name == "search_network_providers":
        results = tools.search_network_providers(
            plan, args["zip_code"], today,
            radius=args.get("radius", 10),
            procedure=args.get("procedure"),
            specialty=args.get("specialty"),
            include_out_of_network=args.get("include_out_of_network", False),
        )
        return {"providers": [r.model_dump() for r in results]}

    if name == "get_benefit_usage":
        return tools.get_benefit_usage(plan, member).model_dump()

    if name == "optimize_treatment_sequence":
        cp = tools.optimize_treatment_sequence(
            plan, member, args["codes"], set(args.get("urgent_codes", [])),
            args.get("network", "in"), today)
        return cp.model_dump()

    if name == "compare_services":
        return tools.compare_services(member, args["codes"], today).model_dump()

    if name == "get_clinic_estimate":
        return tools.get_clinic_estimates(member, args["provider_id"], today).model_dump()

    if name == "create_payment_plan":
        from schemas import PaymentPlanCreate
        from services import payment_plans as pp_svc
        req = PaymentPlanCreate(member_id=member.member_id, provider_id=args["provider_id"],
                                codes=args["codes"], term_months=args.get("term_months", 12))
        return pp_svc.create(req).model_dump()

    if name == "send_payment_plan_to_dentist":
        from services import payment_plans as pp_svc
        return pp_svc.send_to_doctor(args["plan_id"]).model_dump()

    if name == "create_preauth":
        from schemas import PreAuthCreate
        from services import preauth as preauth_svc
        # Amounts come from the coverage engine's out-of-network estimate, never the model.
        est = tools.calculate_coverage(plan, member, args["code"], "out", today)
        req = PreAuthCreate(member_id=member.member_id, provider_id=args["provider_id"], code=args["code"],
                            estimated_cost=est.provider_charge, requested_amount=est.provider_charge,
                            urgency=args.get("urgency", "routine"), reason=args.get("reason", ""))
        return preauth_svc.create(req).model_dump()

    raise KeyError(f"Unknown tool {name!r}")


def _json_default(o: Any):
    if isinstance(o, date):
        return o.isoformat()
    return str(o)


def _client():
    """Create a bedrock-runtime client. boto3 is imported here so it is only required
    when Bedrock is actually used."""
    import boto3  # noqa: WPS433 (lazy import by design)

    region = os.environ.get("AWS_REGION") or os.environ.get("BEDROCK_REGION") or "us-east-1"
    return boto3.client("bedrock-runtime", region_name=region)


def run(message: str, *, plan_id: str = "LFG-123", member_id: str = "demo",
        today: Optional[date] = None, session_id: Optional[str] = None,
        converse: Optional[Callable[..., dict]] = None) -> dict:
    """Run the Bedrock Converse tool-use loop.

    ``converse`` can be injected (a callable with the signature of
    ``bedrock-runtime.converse``) to unit-test the loop without AWS. When omitted, a real
    boto3 client is created and ``BEDROCK_MODEL_ID`` must be set.
    """
    today = today or date.today()
    tracer = Tracer()
    plan = tools.get_plan_details(plan_id)
    member = tools.get_member(member_id)

    model_id = os.environ.get("BEDROCK_MODEL_ID", "")
    if converse is None:
        if not model_id:
            raise RuntimeError("BEDROCK_MODEL_ID is not set; cannot invoke Bedrock.")
        converse = _client().converse

    tool_config = _tool_config()
    messages: list[dict] = [{"role": "user", "content": [{"text": message}]}]
    tool_calls: list[dict] = []
    final_text = ""
    # Engine facts the narration may cite: tool results, plus figures the member themselves typed.
    amounts: set[int] = set()
    pcts: set[int] = set()
    for n in re.findall(r"\d+", message.replace(",", "")):
        amounts.add(int(n))
        pcts.add(int(n))

    for _turn in range(MAX_TURNS):
        with tracer.span("bedrock", "converse", model_id, CALC_VERSION):
            resp = converse(
                modelId=model_id,
                system=[{"text": f"{SYSTEM_PROMPT} Today's date is {today.isoformat()}; use it (and tool-provided periods) for any dates, never guess the year."}],
                messages=messages,
                toolConfig=tool_config,
            )

        out_msg = resp["output"]["message"]
        messages.append(out_msg)
        stop_reason = resp.get("stopReason")

        # Capture any text the model emitted this turn.
        for block in out_msg.get("content", []):
            if "text" in block:
                final_text = block["text"]

        if stop_reason != "tool_use":
            break

        # Execute every requested tool deterministically and feed results back.
        tool_results = []
        for block in out_msg.get("content", []):
            tu = block.get("toolUse")
            if not tu:
                continue
            name, args, tool_use_id = tu["name"], tu.get("input", {}) or {}, tu["toolUseId"]
            with tracer.span("bedrock_tool", name, json.dumps(args, default=_json_default)):
                try:
                    result = _dispatch(name, args, plan=plan, member=member, today=today)
                    status = "success"
                except Exception as exc:  # surface the error to the model, don't crash the loop
                    result = {"error": str(exc)}
                    status = "error"
            tool_calls.append({"tool": name, "input": args, "status": status})
            # Round-trip through JSON so dates/Decimals are plain primitives for the model.
            payload = json.loads(json.dumps(result, default=_json_default))
            collect_facts(payload, amounts, pcts)
            tool_results.append({"toolResult": {
                "toolUseId": tool_use_id,
                "content": [{"json": payload}],
                "status": status,
            }})
        messages.append({"role": "user", "content": tool_results})
    else:
        # Loop exhausted without a natural stop.
        final_text = final_text or "I wasn't able to finish putting this together. Please try rephrasing your request."

    # Output guardrail: every $ / % the model wrote must trace back to an engine fact.
    verified, unverified = check_output(final_text, amounts, pcts)
    if not verified:
        final_text += "\n\n(Please rely on the figures in your estimate; some numbers couldn't be verified.)"

    return {
        "status": "OK",
        "engine": "bedrock",
        "model_id": model_id,
        "session_id": session_id,
        "explanation": final_text,
        "tool_calls": tool_calls,
        "unverified_figures": unverified,
        "trace": [e.model_dump() for e in tracer.events],
        "disclaimer": "Estimates only — actual benefits are determined when the claim is processed.",
    }
