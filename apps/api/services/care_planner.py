"""Care sequencing. Priorities: clinical urgency > dependencies > eligibility > annual max > member cost."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

from schemas import CarePlan, CarePlanItem, CoverageResult, DentalPlan, Member, NetworkStatus, Procedure

Estimator = Callable[[Member, Procedure, date], CoverageResult]


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def _consume(state: Member, r: CoverageResult) -> None:
    state.benefits_used += r.plan_payment
    state.deductible_remaining = max(0.0, state.deductible_remaining - r.deductible_applied)


def optimize_treatment_sequence(plan: DentalPlan, member: Member, procedures: list[Procedure], urgent_codes: set[str],
                                estimate: Estimator, today: date) -> CarePlan:
    order = sorted(procedures, key=lambda p: (p.code not in urgent_codes, p.clinical_priority))
    current = member.model_copy(deep=True)
    next_start = plan.plan_year_end + timedelta(days=1)
    nxt = member.model_copy(deep=True, update={
        "benefits_used": 0.0, "benefits_pending": 0.0, "deductible_remaining": plan.deductible_individual})

    scheduled: dict[str, date] = {}  # family -> scheduled month
    items: list[CarePlanItem] = []
    for proc in order:
        reasons: list[str] = []
        earliest = date(today.year, today.month, 1)
        for fam in proc.prerequisite_families:
            if fam in scheduled:
                earliest = max(earliest, _add_months(scheduled[fam], proc.min_gap_months))
                reasons.append("DEPENDENCY_SCHEDULED_FIRST")
        urgent = proc.code in urgent_codes
        when = max(earliest, today)

        if when > plan.plan_year_end:
            chosen, state, year = estimate(nxt, proc, max(when, next_start)), nxt, next_start.year
            reasons.append("PREREQUISITE_PUSHES_INTO_NEXT_PLAN_YEAR")
            when = max(earliest, next_start)
        else:
            cur = estimate(current, proc, when)
            chosen, state, year = cur, current, plan.plan_year_start.year
            if urgent:
                reasons.append("URGENT_SCHEDULE_EARLIEST")
            elif cur.annual_max_applied:
                alt_date = max(earliest, next_start)
                alt = estimate(nxt, proc, alt_date)
                if alt.covered and alt.member_payment < cur.member_payment:
                    chosen, state, year, when = alt, nxt, next_start.year, alt_date
                    reasons += ["NON_URGENT", "ANNUAL_MAXIMUM_NEARLY_EXHAUSTED", "NEXT_PLAN_YEAR_LOWER_ESTIMATE"]
                else:
                    reasons.append("ANNUAL_MAXIMUM_LIMITS_PAYMENT")
            else:
                reasons.append("WITHIN_REMAINING_MAXIMUM")
        if not chosen.covered:
            reasons.append("NOT_COVERED")
        _consume(state, chosen)
        scheduled[proc.family] = date(when.year, when.month, 1)
        items.append(CarePlanItem(
            code=proc.code, procedure=proc.name, recommended_period=f"{when:%Y-%m}", plan_year=year,
            reason_codes=reasons, estimated_plan_payment=chosen.plan_payment,
            estimated_member_payment=chosen.member_payment, urgent=urgent))

    notes = ["Your dentist should determine the appropriate clinical timing; treatment urgency comes first."]
    if any("NEXT_PLAN_YEAR_LOWER_ESTIMATE" in i.reason_codes for i in items):
        notes.append("Scheduling non-urgent work in the next plan year may allow a new annual maximum to apply.")
    return CarePlan(items=items, total_member_payment=round(sum(i.estimated_member_payment for i in items), 2), notes=notes)
