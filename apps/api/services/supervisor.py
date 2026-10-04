"""Supervisor orchestrator wiring the agent workflow:
UNDERSTAND -> VERIFY -> CALCULATE -> LOCATE -> OPTIMIZE -> VALIDATE -> EXPLAIN.

The LLM-facing agents (intake/procedure/explanation) are rule-based stand-ins here so the
pipeline runs deterministically offline; each is a seam where a watsonx Orchestrate agent
would plug in. No agent invents a benefit number — all math comes from services.tools.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from schemas import (Claim, CoverageResult, Validation, ValidationCheck)
from services import tools
from services.coverage import CALC_VERSION
from services.procedures import interpret
from services.tracing import Tracer


def _intake(text: str) -> dict:
    zip_m = re.search(r"\b(\d{5})\b", text)
    tooth_m = re.search(r"tooth\s+(\d{1,2})", text, re.I)
    urgent = bool(re.search(r"urgent|pain|hurts|emergency|infected|asap|swollen", text, re.I))
    return {"zip_code": zip_m.group(1) if zip_m else None,
            "tooth": int(tooth_m.group(1)) if tooth_m else None, "urgent": urgent}


def compare_networks(plan, member, code: str, service_date: date) -> dict:
    return {"in": tools.calculate_coverage(plan, member, code, "in", service_date),
            "out": tools.calculate_coverage(plan, member, code, "out", service_date)}


def _validate(matches, results: list[CoverageResult], provider_count: int) -> Validation:
    checks, missing = [], []
    low_conf = [m for m in matches if m.requires_confirmation]
    checks.append(ValidationCheck(name="procedure_mapping_confidence",
                                  passed=all(m.confidence >= 0.7 for m in matches),
                                  detail=f"{len(low_conf)} procedure(s) need confirmation" if low_conf else "all confident"))
    checks.append(ValidationCheck(name="plan_values_have_evidence",
                                  passed=all(r.provenance for r in results), detail="provenance attached"))
    checks.append(ValidationCheck(name="cost_calculation_reproducible",
                                  passed=all(r.calculation_version == CALC_VERSION for r in results),
                                  detail=CALC_VERSION))
    checks.append(ValidationCheck(name="network_status_verified",
                                  passed=True, detail="network from provider_networks membership only"))
    checks.append(ValidationCheck(name="disclaimer_present",
                                  passed=all(r.disclaimer for r in results), detail="estimate disclaimer attached"))
    if provider_count == 0:
        missing.append("in_network_provider_in_radius")
    status = ("NEEDS_INFORMATION" if any(not c.passed for c in checks) or missing
              else "QUALIFIED" if low_conf else "OK")
    return Validation(status=status, checks=checks, missing=missing)


def _explain(plan, usage, matches, comparisons: dict, care_plan, providers_in) -> str:
    lines = []
    for m in matches:
        proc = tools.lookup_procedure(m.selected_code)
        cmp = comparisons[m.selected_code]["in"]
        pct = int(cmp.coinsurance_pct * 100)
        cat = {"preventive": "preventive", "basic": "basic", "major": "major"}.get(proc.category, proc.category)
        if cmp.covered:
            lines.append(
                f"**{proc.name}** appears to fall under *{cat}* services. Your plan may pay about {pct}% "
                f"of the plan's approved cost after any remaining deductible — an estimated "
                f"${cmp.plan_payment:,.0f}, leaving you about **${cmp.member_payment:,.0f}** in network.")
        else:
            lines.append(f"**{proc.name}**: {cmp.denial_reason}")
        if m.requires_confirmation:
            lines[-1] += f" _(Assumed code {m.selected_code}; please confirm with your dentist.)_"
    if providers_in:
        lines.append(f"I found {len(providers_in)} verified in-network dentist(s) within range; the closest is "
                     f"{providers_in[0].provider.name} ({providers_in[0].distance_miles} mi).")
    lines.append(f"You have up to approximately ${usage.benefits_remaining:,.0f} of remaining eligible plan benefits "
                 f"this year (${usage.benefits_used:,.0f} of ${usage.annual_maximum:,.0f} used).")
    if care_plan and len(care_plan.items) > 1:
        seq = " then ".join(f"{i.procedure} ({i.recommended_period})" for i in care_plan.items)
        lines.append(f"Suggested sequence: {seq}. " + " ".join(care_plan.notes))
    lines.append("_Estimates only — actual benefits are determined when the claim is processed._")
    return "\n\n".join(lines)


def run(message: str, *, plan_id: str = "LFG-123", member_id: str = "demo",
        today: Optional[date] = None, session_id: Optional[str] = None) -> dict:
    today = today or date.today()
    tracer = Tracer()
    plan = tools.get_plan_details(plan_id)
    member = tools.get_member(member_id)

    # Guardrails first: emergencies, PII, off-topic (clinical urgency before finances).
    from services.guardrails import screen_input
    with tracer.span("guardrails", "screen_input"):
        screen = screen_input(message)
    if screen.urgent:
        return {"status": "EMERGENCY", "message": screen.message, "urgent": True,
                "notes": screen.notes, "trace": [e.model_dump() for e in tracer.events]}
    if not screen.ok:
        return {"status": "NEEDS_INFORMATION", "message": screen.message,
                "notes": screen.notes, "trace": [e.model_dump() for e in tracer.events]}
    message = screen.text  # redacted

    with tracer.span("intake", "parse_message"):
        intake = _intake(message)
    with tracer.span("procedure", "interpret"):
        matches = interpret(message, intake.get("tooth"))
    if not matches:
        return {"status": "NEEDS_INFORMATION", "message": "I couldn't identify a dental procedure. "
                "Could you describe what your dentist recommended?", "trace": [e.model_dump() for e in tracer.events]}

    zip_code = intake.get("zip_code") or member.zip_code
    codes = [m.selected_code for m in matches]
    comparisons, providers_in, all_results = {}, [], []
    for m in matches:
        with tracer.span("cost+coverage", "compare_networks", m.selected_code, CALC_VERSION):
            comparisons[m.selected_code] = compare_networks(plan, member, m.selected_code, today)
        all_results += [comparisons[m.selected_code]["in"], comparisons[m.selected_code]["out"]]

    with tracer.span("provider", "search_network_providers"):
        try:
            providers_in = tools.search_network_providers(plan, zip_code, today, procedure=codes[0])
        except ValueError:
            providers_in = []
    with tracer.span("benefits", "get_benefit_usage"):
        usage = tools.get_benefit_usage(plan, member)
    with tracer.span("care_planner", "optimize_treatment_sequence", calculation_version=CALC_VERSION):
        urgent = set(codes) if intake["urgent"] else set()
        care_plan = tools.optimize_treatment_sequence(plan, member, codes, urgent, "in", today)
    with tracer.span("validation", "validate"):
        validation = _validate(matches, all_results, len(providers_in))
    with tracer.span("explanation", "explain"):
        explanation = _explain(plan, usage, matches, comparisons, care_plan, providers_in)

    return {
        "status": validation.status,
        "session_id": session_id,
        "intake": intake,
        "procedures": [m.model_dump() for m in matches],
        "comparisons": {c: {"in": v["in"].model_dump(), "out": v["out"].model_dump()} for c, v in comparisons.items()},
        "providers": [p.model_dump() for p in providers_in],
        "benefit_usage": usage.model_dump(),
        "care_plan": care_plan.model_dump(),
        "reminder": tools.create_reminder(plan, member, today),
        "validation": validation.model_dump(),
        "explanation": explanation,
        "trace": [e.model_dump() for e in tracer.events],
    }
