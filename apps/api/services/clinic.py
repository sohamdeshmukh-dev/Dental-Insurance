"""Per-clinic pre-estimates: a clinic's service fee list run through the deterministic engine.

Fees are mock (BASE_FEES x regional factor x the clinic's fee_factor); the member's cost is
computed by the coverage engine for the clinic's network status. No LLM involved.
"""
from __future__ import annotations

from datetime import date

from data.mock import BASE_FEES, PLAN, ZIP_FACTORS
from schemas import ClinicEstimates, ClinicServiceEstimate, Member
from services import coverage, procedures
from services.providers import active_membership, get_provider

_DISC = "Estimated — mock fee schedule. Actual cost and benefits are determined when the claim is processed."


def clinic_estimates(member: Member, provider_id: str, on: date) -> ClinicEstimates:
    p = get_provider(provider_id)
    net = "in" if active_membership(provider_id, PLAN.network_id, on) else "out"
    services: list[ClinicServiceEstimate] = []
    for code in p.procedures:
        if code not in procedures.CATALOG or code not in BASE_FEES:
            continue
        proc = procedures.CATALOG[code]
        allowed = round(BASE_FEES[code] * ZIP_FACTORS.get(p.zip_code[:3], 1.05) * p.fee_factor, 2)
        billed = round(allowed * 1.25, 2)
        r = coverage.calculate_coverage(PLAN, member, proc, net, allowed, billed, on)
        services.append(ClinicServiceEstimate(
            code=code, name=proc.name, category=proc.category, allowed_amount=r.allowed_amount,
            member_pays=r.member_payment, covered=r.covered))
    services.sort(key=lambda s: s.member_pays)
    return ClinicEstimates(provider_id=p.provider_id, provider_name=p.name,
                           network="in" if net == "in" else "out", services=services, disclaimer=_DISC)
