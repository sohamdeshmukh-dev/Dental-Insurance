"""Annual maximum tracker and unused-benefit reminders."""
from __future__ import annotations

from datetime import date
from typing import Optional

from schemas import BenefitUsage, DentalPlan, Member

REMINDER_WINDOW_DAYS = 90


def get_benefit_usage(plan: DentalPlan, member: Member) -> BenefitUsage:
    remaining = max(0.0, plan.annual_maximum - member.benefits_used - member.benefits_pending)
    pct = round((member.benefits_used + member.benefits_pending) / plan.annual_maximum * 100, 1)
    state = "plenty_remaining" if pct < 50 else "moderate_utilization" if pct < 80 else "near_annual_maximum"
    return BenefitUsage(annual_maximum=plan.annual_maximum, benefits_used=member.benefits_used,
                        benefits_pending=member.benefits_pending, benefits_remaining=remaining, percent_used=pct,
                        state=state, plan_year_end=plan.plan_year_end, deductible_remaining=member.deductible_remaining)


def create_reminder(usage: BenefitUsage, today: date) -> Optional[str]:
    days_left = (usage.plan_year_end - today).days
    if usage.benefits_remaining <= 0 or not 0 <= days_left <= REMINDER_WINDOW_DAYS:
        return None
    # Never frame the maximum as money the member is "losing".
    return (f"You have up to approximately ${usage.benefits_remaining:,.0f} of remaining eligible plan benefits "
            f"of your ${usage.annual_maximum:,.0f} annual maximum. Your benefits reset on "
            f"{usage.plan_year_end.replace(year=usage.plan_year_end.year + 1, month=1, day=1):%B %-d}.")

_MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def get_funding_timeline(plan: DentalPlan, member: Member, today: date) -> "FundingTimeline":
    """Deterministic month-by-month view of how much plan funding has been used/remains.

    Built from the member's paid claims (the source of truth), so cumulative_used at year end
    equals benefits_used. Months with no claims carry the running total forward.
    """
    from schemas import FundingMonth, FundingTimeline

    year = plan.plan_year_start.year
    paid_by_month = [0.0] * 12
    by_category: dict[str, float] = {}
    for c in member.claims:
        if c.service_date.year == year:
            paid_by_month[c.service_date.month - 1] += c.plan_paid
            by_category[c.category] = round(by_category.get(c.category, 0.0) + c.plan_paid, 2)

    months, cumulative = [], 0.0
    for i in range(12):
        cumulative = round(cumulative + paid_by_month[i], 2)
        months.append(FundingMonth(
            month=f"{year}-{i + 1:02d}", label=_MONTH_LABELS[i],
            paid_in_month=round(paid_by_month[i], 2), cumulative_used=cumulative,
            remaining=round(max(0.0, plan.annual_maximum - cumulative), 2)))

    usage = get_benefit_usage(plan, member)
    days_left = max(0, (plan.plan_year_end - today).days)
    note = (f"${usage.benefits_remaining:,.0f} of your ${plan.annual_maximum:,.0f} annual maximum is still "
            f"available with {days_left} days left in the plan year — unused benefits do not roll over."
            if days_left else "The plan year has ended; benefits reset to the full annual maximum.")
    return FundingTimeline(
        annual_maximum=plan.annual_maximum, benefits_used=usage.benefits_used,
        benefits_pending=usage.benefits_pending, benefits_remaining=usage.benefits_remaining,
        percent_used=usage.percent_used, deductible_individual=plan.deductible_individual,
        deductible_remaining=member.deductible_remaining, plan_year_start=plan.plan_year_start,
        plan_year_end=plan.plan_year_end, months=months, by_category=by_category,
        projected_unused_at_year_end=usage.benefits_remaining, note=note)
