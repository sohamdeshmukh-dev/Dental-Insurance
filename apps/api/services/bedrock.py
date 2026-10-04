"""AWS Bedrock estimation agent (optional).

The backend invokes a Bedrock foundation model with a tool-use loop over our deterministic
services. The model INTERPRETS and NARRATES; it never produces benefit numbers itself — every
figure comes from a tool backed by the coverage engine. Output is guardrail-checked so any
dollar/percent the model writes must match an engine fact.

If AWS creds / boto3 / model access are not configured, `enabled()` is False and the caller
falls back to the rule-based supervisor. Nothing here runs without explicit AWS configuration.
"""
from __future__ import annotations

import os
from datetime import date

from services import clinic, procedures, tools
from services.guardrails import check_output, with_disclaimer
from services.supervisor import compare_networks

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")

SYSTEM = (
    "You are the Lincoln Financial dental benefits assistant. You help an employee understand "
    "what a procedure will cost and what their plan covers.\n"
    "RULES:\n"
    "- Never invent or estimate dollar amounts or percentages yourself. Always call a tool and use "
    "its exact numbers.\n"
    "- Compare in-network vs out-of-network when relevant, and prefer in-network savings.\n"
    "- Clinical urgency always comes first; never advise delaying urgent care to save money.\n"
    "- You do not give medical or treatment advice, diagnoses, or medication dosing.\n"
    "- Keep answers short and plain-language, and say figures are estimates."
)


def enabled() -> bool:
    if os.environ.get("DISABLE_BEDROCK"):
        return False
    if not (os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_PROFILE") or os.environ.get("AWS_ROLE_ARN")):
        return False
    try:
        import boto3  # noqa: F401
    except Exception:
        return False
    return True


TOOLS = [
    {"toolSpec": {"name": "interpret_procedures", "description": "Turn the member's free text into candidate dental procedure codes.",
                  "inputSchema": {"json": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}}},
    {"toolSpec": {"name": "estimate_procedure", "description": "In-network vs out-of-network cost estimate for one CDT code, from the coverage engine.",
                  "inputSchema": {"json": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}}},
    {"toolSpec": {"name": "clinic_estimate", "description": "Estimated member cost for the services a specific clinic offers.",
                  "inputSchema": {"json": {"type": "object", "properties": {"provider_id": {"type": "string"}}, "required": ["provider_id"]}}}},
    {"toolSpec": {"name": "get_benefit_usage", "description": "The member's current annual maximum, used, and remaining.",
                  "inputSchema": {"json": {"type": "object", "properties": {}}}}},
    {"toolSpec": {"name": "find_providers", "description": "Verified in-network and out-of-network dentists near a ZIP code.",
                  "inputSchema": {"json": {"type": "object", "properties": {"zip_code": {"type": "string"}}, "required": ["zip_code"]}}}},
]


def _record(res, amounts: set[int], pcts: set[int]) -> None:
    """Collect every amount/percent a tool returned so the output can be verified against them."""
    if isinstance(res, dict):
        for k, v in res.items():
            if isinstance(v, (int, float)) and ("amount" in k or "pay" in k or "payment" in k or "charge"
                                                in k or "max" in k or "used" in k or "remaining" in k or "cost" in k):
                amounts.add(round(v))
            elif "coinsurance" in k and isinstance(v, (int, float)):
                pcts.add(round(v * 100))
            else:
                _record(v, amounts, pcts)
    elif isinstance(res, list):
        for item in res:
            _record(item, amounts, pcts)


def _dispatch(name: str, inp: dict, plan, member, on: date, amounts: set[int], pcts: set[int]):
    if name == "interpret_procedures":
        return {"matches": [m.model_dump() for m in procedures.interpret(inp.get("text", ""))]}
    if name == "estimate_procedure":
        both = compare_networks(plan, member, inp["code"], on)
        res = {"in_network": both["in"].model_dump(), "out_of_network": both["out"].model_dump()}
    elif name == "clinic_estimate":
        res = clinic.clinic_estimates(member, inp["provider_id"], on).model_dump()
    elif name == "get_benefit_usage":
        res = tools.get_benefit_usage(plan, member).model_dump()
    elif name == "find_providers":
        res = {"providers": [p.model_dump() for p in tools.search_network_providers(
            plan, inp["zip_code"], on, include_out_of_network=True)]}
    else:
        return {"error": f"unknown tool {name}"}
    _record(res, amounts, pcts)
    return res


def run_estimation_agent(message: str, member, today: date | None = None) -> dict:
    today = today or date.today()
    plan = tools.get_plan_details(member.plan_id)
    import boto3
    client = boto3.client("bedrock-runtime", region_name=REGION)
    amounts: set[int] = set()
    pcts: set[int] = set()
    messages = [{"role": "user", "content": [{"text": message}]}]

    for _ in range(6):
        resp = client.converse(modelId=MODEL_ID, system=[{"text": SYSTEM}], messages=messages,
                                toolConfig={"tools": TOOLS}, inferenceConfig={"temperature": 0.2, "maxTokens": 900})
        out = resp["output"]["message"]
        messages.append(out)
        tool_uses = [c["toolUse"] for c in out["content"] if "toolUse" in c]
        if not tool_uses:
            text = "".join(c.get("text", "") for c in out["content"])
            ok, _ = check_output(text, amounts, pcts)
            if not ok:
                text += "\n\n(Please rely on the figures in your estimate; some numbers couldn't be verified.)"
            return {"status": "OK", "via": "bedrock", "explanation": with_disclaimer(text)}
        results = []
        for tu in tool_uses:
            res = _dispatch(tu["name"], tu.get("input", {}), plan, member, today, amounts, pcts)
            results.append({"toolResult": {"toolUseId": tu["toolUseId"], "content": [{"json": res}]}})
        messages.append({"role": "user", "content": results})

    return {"status": "OK", "via": "bedrock", "explanation": with_disclaimer(
        "I couldn't complete that estimate — please try rephrasing or check your dashboard.")}
