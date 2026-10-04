"""Narrowly scoped tools. Agents call these; they never touch data stores directly."""
from __future__ import annotations

from datetime import date
from typing import Optional

from data.mock import MEMBERS, PLAN
from schemas import CarePlan, CoverageResult, DentalPlan, Member, NetworkStatus, Procedure, ProviderResult
from services import benefits, care_planner, coverage, procedures, providers
from services.cost import CostDataProvider, MockCostDataProvider
from services.geo import Geocoder, default_geocoder

cost_provider: CostDataProvider = MockCostDataProvider()
geocoder: Geocoder = default_geocoder()


def get_plan_details(plan_id: str) -> DentalPlan:
    if plan_id != PLAN.plan_id:
        raise KeyError(f"Unknown plan {plan_id}")
    return PLAN


def get_member(member_id: str) -> Member:
    return MEMBERS[member_id]


def lookup_procedure(code: str) -> Procedure:
    return procedures.CATALOG[code]


def estimate_local_cost(code: str, zip_code: str):
    return cost_provider.get_estimated_cost(code, zip_code)


def calculate_coverage(plan: DentalPlan, member: Member, code: str, network: NetworkStatus,
                       service_date: date) -> CoverageResult:
    c = estimate_local_cost(code, member.zip_code)
    return coverage.calculate_coverage(plan, member, lookup_procedure(code), network,
                                       c.allowed_in_network, c.typical_charge, service_date)


def search_network_providers(plan: DentalPlan, zip_code: str, on: date, radius: float = 10, procedure: Optional[str] = None,
                             specialty: Optional[str] = None, include_out_of_network: bool = False) -> list[ProviderResult]:
    return providers.search_providers(geocoder, zip_code=zip_code, radius=radius, network_id=plan.network_id, on=on,
                                      specialty=specialty, procedure=procedure,
                                      include_out_of_network=include_out_of_network)


def get_benefit_usage(plan: DentalPlan, member: Member):
    return benefits.get_benefit_usage(plan, member)


def create_reminder(plan: DentalPlan, member: Member, today: date):
    return benefits.create_reminder(benefits.get_benefit_usage(plan, member), today)


def optimize_treatment_sequence(plan: DentalPlan, member: Member, codes: list[str], urgent_codes: set[str],
                                network: NetworkStatus, today: date) -> CarePlan:
    est = lambda m, p, d: calculate_coverage(plan, m, p.code, network, d)
    return care_planner.optimize_treatment_sequence(plan, member, [lookup_procedure(c) for c in codes],
                                                    urgent_codes, est, today)


def get_funding_timeline(plan: DentalPlan, member: Member, today: date):
    return benefits.get_funding_timeline(plan, member, today)


def get_rewards(plan: DentalPlan, member: Member, lifetime_bonus: int | None = None,
                redeemed_points: int = 0, extra_entries: int = 0):
    from services import rewards
    # Guardian has prior-year lifetime points (demo); dependents start fresh this year.
    if lifetime_bonus is None:
        lifetime_bonus = 1180 if member.relationship == "guardian" else 0
    return rewards.compute_rewards(plan, member, lifetime_bonus=lifetime_bonus,
                                   redeemed_points=redeemed_points, extra_entries=extra_entries)


def get_account():
    from data.mock import ACCOUNT
    from schemas import Account, MemberSummary
    members = []
    for mid in ACCOUNT["member_ids"]:
        m = MEMBERS[mid]
        u = benefits.get_benefit_usage(PLAN, m)
        members.append(MemberSummary(
            member_id=m.member_id, name=m.name, relationship=m.relationship, age=m.age,
            annual_maximum=u.annual_maximum, benefits_used=u.benefits_used,
            benefits_remaining=u.benefits_remaining, percent_used=u.percent_used, state=u.state))
    return Account(account_id=ACCOUNT["account_id"], employer=ACCOUNT["employer"], plan_name=PLAN.plan_name,
                   guardian_id=ACCOUNT["guardian_id"], members=members)
