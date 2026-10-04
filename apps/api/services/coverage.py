"""Deterministic coverage engine. No LLM is involved in any number produced here."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from schemas import (CoverageResult, DentalPlan, Member, NetworkStatus, Procedure, Step)

CALC_VERSION = "coverage-1.0.0"
DISCLAIMER = "Estimated — actual benefits are determined when the claim is processed."
D = Decimal


def money(x) -> Decimal:
    return D(str(x)).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month - (1 if end.day < start.day else 0)


@dataclass
class ClaimContext:
    plan: DentalPlan
    member: Member
    procedure: Procedure
    network: NetworkStatus
    allowed: Decimal
    billed: Decimal
    service_date: date
    covered: bool = True
    denial_reason: Optional[str] = None
    deductible_applied: Decimal = D(0)
    coinsurance: Decimal = D(0)
    payment_before_max: Decimal = D(0)
    plan_payment: Decimal = D(0)
    max_applied: bool = False
    max_remaining_after: Optional[Decimal] = None
    provider_charge: Decimal = D(0)
    steps: list[Step] = field(default_factory=list)

    def note(self, rule: str, text: str, amount: Optional[Decimal] = None):
        self.steps.append(Step(rule=rule, description=text, amount=float(amount) if amount is not None else None))

    def deny(self, rule: str, reason: str):
        self.covered, self.denial_reason = False, reason
        self.note(rule, reason)


class Rule:
    name = "Rule"

    def apply(self, ctx: ClaimContext) -> None:  # pragma: no cover
        raise NotImplementedError


class ExclusionRule(Rule):
    name = "ExclusionRule"

    def apply(self, ctx):
        if ctx.procedure.code in ctx.plan.exclusions:
            ctx.deny(self.name, f"{ctx.procedure.code} is excluded under the plan.")


class WaitingPeriodRule(Rule):
    name = "WaitingPeriodRule"

    def apply(self, ctx):
        for wp in ctx.plan.waiting_periods:
            if wp.category == ctx.procedure.category:
                elapsed = months_between(ctx.member.coverage_effective_date, ctx.service_date)
                if elapsed < wp.months:
                    ctx.deny(self.name, f"{wp.months}-month waiting period for {wp.category} services not yet satisfied.")
                else:
                    ctx.note(self.name, f"{wp.months}-month waiting period for {wp.category} services satisfied.")


class FrequencyLimitRule(Rule):
    name = "FrequencyLimitRule"

    def apply(self, ctx):
        for lim in ctx.plan.frequency_limits:
            if ctx.procedure.code not in lim.codes:
                continue
            recent = [h for h in ctx.member.history
                      if h.code in lim.codes and 0 <= months_between(h.service_date, ctx.service_date) < lim.period_months]
            if len(recent) >= lim.count:
                ctx.deny(self.name, f"Frequency limit reached ({lim.count} per {lim.period_months} months).")
            else:
                ctx.note(self.name, f"Within frequency limit ({len(recent)} of {lim.count} used in {lim.period_months} months).")


class NetworkRule(Rule):
    name = "NetworkRule"

    def apply(self, ctx):
        table = ctx.plan.coinsurance_in_network if ctx.network == "in" else ctx.plan.coinsurance_out_of_network
        ctx.coinsurance = D(str(table[ctx.procedure.category]))
        if ctx.network == "in":
            ctx.provider_charge = ctx.allowed  # contracted fee: no balance billing
            ctx.note(self.name, "In-network: provider accepts the plan's allowed amount as full payment.", ctx.allowed)
        else:
            ctx.provider_charge = max(ctx.billed, ctx.allowed)
            ctx.note(self.name, "Out-of-network: plan pays on its allowed amount; you may owe the difference.", ctx.provider_charge)


class DeductibleRule(Rule):
    name = "DeductibleRule"

    def apply(self, ctx):
        if ctx.procedure.category in ctx.plan.deductible_exempt:
            ctx.note(self.name, f"Deductible does not apply to {ctx.procedure.category} services.", D(0))
            return
        ctx.deductible_applied = min(money(ctx.member.deductible_remaining), ctx.allowed)
        ctx.note(self.name, "Remaining deductible applied to the allowed amount.", ctx.deductible_applied)


class CoinsuranceRule(Rule):
    name = "CoinsuranceRule"

    def apply(self, ctx):
        eligible = ctx.allowed - ctx.deductible_applied
        ctx.payment_before_max = money(eligible * ctx.coinsurance)
        ctx.note(self.name, f"Plan pays {int(ctx.coinsurance * 100)}% of {eligible} after deductible.", ctx.payment_before_max)


class AnnualMaximumRule(Rule):
    name = "AnnualMaximumRule"

    def apply(self, ctx):
        remaining = max(D(0), money(ctx.plan.annual_maximum) - money(ctx.member.benefits_used) - money(ctx.member.benefits_pending))
        ctx.plan_payment = min(ctx.payment_before_max, remaining)
        ctx.max_applied = ctx.plan_payment < ctx.payment_before_max
        ctx.max_remaining_after = remaining - ctx.plan_payment
        ctx.note(self.name, f"Plan payment limited by ${remaining} remaining annual maximum." if ctx.max_applied
                 else f"Within ${remaining} remaining annual maximum.", ctx.plan_payment)


PIPELINE: list[Rule] = [ExclusionRule(), WaitingPeriodRule(), FrequencyLimitRule(), NetworkRule(),
                        DeductibleRule(), CoinsuranceRule(), AnnualMaximumRule()]
_ALWAYS = (NetworkRule,)  # still needed to know what the member owes when denied


def calculate_coverage(plan: DentalPlan, member: Member, procedure: Procedure, network: NetworkStatus,
                       allowed: float, billed: float, service_date: date) -> CoverageResult:
    ctx = ClaimContext(plan, member, procedure, network, money(allowed), money(billed), service_date)
    for rule in PIPELINE:
        if ctx.covered or isinstance(rule, _ALWAYS):
            rule.apply(ctx)
    member_payment = ctx.provider_charge - ctx.plan_payment
    prov = {k: v for k, v in plan.provenance.items()
            if k in ("annual_maximum", "deductible_individual", "waiting_periods", "frequency_limits")
            or k.startswith(f"coinsurance_in_network.{procedure.category}")
            or k.startswith("coinsurance_out_of_network")}
    return CoverageResult(
        code=procedure.code, network=network, covered=ctx.covered, denial_reason=ctx.denial_reason,
        provider_charge=float(ctx.provider_charge), allowed_amount=float(ctx.allowed),
        deductible_applied=float(ctx.deductible_applied), coinsurance_pct=float(ctx.coinsurance),
        plan_payment_before_max=float(ctx.payment_before_max), plan_payment=float(ctx.plan_payment),
        member_payment=float(member_payment), annual_max_applied=ctx.max_applied,
        annual_max_remaining_after=None if ctx.max_remaining_after is None else float(ctx.max_remaining_after),
        steps=ctx.steps,
        provenance=prov, calculation_version=CALC_VERSION, disclaimer=DISCLAIMER)


def in_network_savings(in_net: CoverageResult, out_net: CoverageResult) -> float:
    """How much less the member pays in-network than out-of-network for the same code."""
    return float(money(out_net.member_payment) - money(in_net.member_payment))
