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
    "than guessing. Always end with a reminder that estimates are not final and that actual "
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
