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
