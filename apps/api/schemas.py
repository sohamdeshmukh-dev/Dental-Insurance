from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal["preventive", "basic", "major", "ortho"]
NetworkStatus = Literal["in", "out"]


class Provenance(BaseModel):
    source_type: Literal["PLAN_DOCUMENT", "LINCOLN_API", "USER_PROVIDED", "MOCK"]
    source_id: str
    page: Optional[int] = None
    confidence: float = 1.0


class WaitingPeriod(BaseModel):
    category: Category
    months: int


class FrequencyLimit(BaseModel):
    codes: list[str]
    count: int
    period_months: int


class DentalPlan(BaseModel):
    plan_id: str
    plan_name: str
    network_type: Literal["PPO", "DHMO", "Other"]
    network_id: str
    deductible_individual: float
    annual_maximum: float
    coinsurance_in_network: dict[Category, float]
    coinsurance_out_of_network: dict[Category, float]
    deductible_exempt: list[Category] = ["preventive"]
    plan_year_start: date
    plan_year_end: date
    waiting_periods: list[WaitingPeriod] = []
    exclusions: list[str] = []  # CDT codes
    frequency_limits: list[FrequencyLimit] = []
    provenance: dict[str, Provenance] = {}


class ServiceRecord(BaseModel):
    code: str
    service_date: date


class PaidClaim(BaseModel):
    service_date: date
    code: str
    description: str
    category: Category
    plan_paid: float
    member_paid: float
    network: NetworkStatus = "in"


class Member(BaseModel):
    member_id: str
    plan_id: str
    zip_code: str
    coverage_effective_date: date
    benefits_used: float = 0
    benefits_pending: float = 0
    deductible_remaining: float = 0
    history: list[ServiceRecord] = []
    claims: list[PaidClaim] = []


class Procedure(BaseModel):
    code: str
    name: str
    category: Category
    family: str
    clinical_priority: int  # lower = earlier
    prerequisite_families: list[str] = []
    min_gap_months: int = 0
    description: str = ""


class ProcedureMatch(BaseModel):
    procedure: str
    possible_codes: list[str]
    selected_code: str
    confidence: float
    requires_confirmation: bool
    note: str = ""


class Step(BaseModel):
    rule: str
    description: str
    amount: Optional[float] = None


class CoverageResult(BaseModel):
    code: str
    network: NetworkStatus
    covered: bool
    denial_reason: Optional[str] = None
    provider_charge: float
    allowed_amount: float
    deductible_applied: float
    coinsurance_pct: float
    plan_payment_before_max: float
    plan_payment: float
    member_payment: float
    annual_max_applied: bool
    steps: list[Step]
    provenance: dict[str, Provenance] = {}
    calculation_version: str
    disclaimer: str


class Provider(BaseModel):
    provider_id: str
    name: str
    specialty: str
    address: str
    city: str
    state: str
    zip_code: str
    latitude: float
    longitude: float
    phone: str
    accepting_new_patients: bool = True
    procedures: list[str] = []  # CDT codes offered


class ProviderNetwork(BaseModel):
    provider_id: str
    network_id: str
    effective_date: date
    termination_date: Optional[date] = None
    verification_timestamp: str
    source: str


class ProviderResult(BaseModel):
    provider: Provider
    distance_miles: float
    network_status: Literal["VERIFIED_IN_NETWORK", "OUT_OF_NETWORK"]
    verified_source: Optional[str] = None
    verified_at: Optional[str] = None


class BenefitUsage(BaseModel):
    annual_maximum: float
    benefits_used: float
    benefits_pending: float
    benefits_remaining: float
    percent_used: float
    state: Literal["plenty_remaining", "moderate_utilization", "near_annual_maximum"]
    plan_year_end: date
    deductible_remaining: float


class CarePlanItem(BaseModel):
    code: str
    procedure: str
    recommended_period: str  # YYYY-MM
    plan_year: int
    reason_codes: list[str]
    estimated_plan_payment: float
    estimated_member_payment: float
    urgent: bool = False


class CarePlan(BaseModel):
    items: list[CarePlanItem]
    total_member_payment: float
    notes: list[str]


class CarePlanRequest(BaseModel):
    codes: list[str]
    urgent_codes: list[str] = []
    network: NetworkStatus = "in"
    today: Optional[date] = None


class EstimateRequest(BaseModel):
    plan_id: str = "LFG-123"
    procedure_code: str
    provider_id: Optional[str] = None
    zip_code: Optional[str] = None


class InterpretRequest(BaseModel):
    text: str


class AgentMessage(BaseModel):
    session_id: Optional[str] = None
    message: str
    today: Optional[date] = None


class Claim(BaseModel):
    claim: str
    source_type: str
    source_id: str
    page: Optional[int] = None
    confidence: float


class ValidationCheck(BaseModel):
    name: str
    passed: bool
    detail: str = ""


class Validation(BaseModel):
    status: Literal["OK", "QUALIFIED", "NEEDS_INFORMATION"]
    checks: list[ValidationCheck]
    missing: list[str] = Field(default_factory=list)


class TraceEvent(BaseModel):
    agent: str
    tool: str
    latency_ms: float
    detail: str = ""
    calculation_version: Optional[str] = None


# ---------------------------------------------------------------------------
# Funding dashboard
# ---------------------------------------------------------------------------
class FundingMonth(BaseModel):
    month: str  # YYYY-MM
    label: str  # e.g. "Mar"
    paid_in_month: float
    cumulative_used: float
    remaining: float


class FundingTimeline(BaseModel):
    annual_maximum: float
    benefits_used: float
    benefits_pending: float
    benefits_remaining: float
    percent_used: float
    deductible_individual: float
    deductible_remaining: float
    plan_year_start: date
    plan_year_end: date
    months: list[FundingMonth]
    by_category: dict[str, float]
    projected_unused_at_year_end: float
    note: str


# ---------------------------------------------------------------------------
# Loyalty / rewards  (PROTOTYPE — illustrative values, not a live financial product)
# ---------------------------------------------------------------------------
class RewardEvent(BaseModel):
    event_date: date
    code: str
    description: str
    points: int


class RewardItem(BaseModel):
    id: str
    name: str
    type: Literal["gift_card", "sweepstakes", "cash_sweepstakes", "discount"]
    cost_points: int
    value: str
    detail: str
    affordable: bool = False
    demo: bool = True


class RewardTier(BaseModel):
    name: str
    min_points: int
    multiplier: float
    perks: list[str]


class RewardsProfile(BaseModel):
    member_id: str
    points_balance: int
    lifetime_points: int
    tier: str
    tier_multiplier: float
    next_tier: Optional[str]
    points_to_next_tier: int
    tier_progress_pct: float
    tiers: list[RewardTier]
    ledger: list[RewardEvent]
    catalog: list[RewardItem]
    sweepstakes_entries: int
    earn_rules: list[str]
    disclaimer: str


class RedeemRequest(BaseModel):
    item_id: str


class RedeemResult(BaseModel):
    ok: bool
    message: str
    points_balance: int
    sweepstakes_entries: int
