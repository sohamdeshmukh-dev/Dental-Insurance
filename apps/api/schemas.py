from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

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


Relationship = Literal["guardian", "dependent"]


class Member(BaseModel):
    member_id: str
    plan_id: str
    zip_code: str
    coverage_effective_date: date
    name: str = "Member"
    relationship: Relationship = "guardian"
    age: Optional[int] = None
    benefits_used: float = 0
    benefits_pending: float = 0
    deductible_remaining: float = 0
    history: list[ServiceRecord] = []
    claims: list[PaidClaim] = []


class MemberSummary(BaseModel):
    member_id: str
    name: str
    relationship: Relationship
    age: Optional[int] = None
    annual_maximum: float
    benefits_used: float
    benefits_remaining: float
    percent_used: float
    state: Literal["plenty_remaining", "moderate_utilization", "near_annual_maximum"]


class Account(BaseModel):
    account_id: str
    employer: str
    plan_name: str
    guardian_id: str
    members: list[MemberSummary]


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
    annual_max_remaining_after: Optional[float] = None  # None when the claim is denied
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
    fee_factor: float = 1.0     # clinic-specific fee level vs regional baseline (mock)


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
    member_id: str = "demo"


class EstimateRequest(BaseModel):
    plan_id: str = "LFG-123"
    procedure_code: str
    provider_id: Optional[str] = None
    zip_code: Optional[str] = None
    member_id: str = "demo"


class InterpretRequest(BaseModel):
    text: str


class AgentMessage(BaseModel):
    session_id: Optional[str] = None
    message: str
    today: Optional[date] = None
    member_id: str = "demo"


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
    member_id: str = "demo"


class RedeemResult(BaseModel):
    ok: bool
    message: str
    points_balance: int
    sweepstakes_entries: int


# ---------------------------------------------------------------------------
# Per-clinic pre-estimates
# ---------------------------------------------------------------------------
class ClinicServiceEstimate(BaseModel):
    code: str
    name: str
    category: str
    allowed_amount: float
    member_pays: float
    covered: bool


class ClinicEstimates(BaseModel):
    provider_id: str
    provider_name: str
    network: NetworkStatus
    services: list[ClinicServiceEstimate]
    disclaimer: str


# ---------------------------------------------------------------------------
# Out-of-network pre-authorization  (SIMULATED — mock Lincoln approval)
# ---------------------------------------------------------------------------
Urgency = Literal["routine", "soon", "urgent"]


class PreAuthCreate(BaseModel):
    member_id: str = "demo"
    provider_id: str
    code: str
    estimated_cost: float = Field(ge=0)
    requested_amount: float = Field(ge=0)
    urgency: Urgency = "routine"
    reason: str = ""


class PreAuth(BaseModel):
    id: str
    member_id: str
    member_name: str
    provider_id: str
    provider_name: str
    code: str
    procedure_name: str
    estimated_cost: float
    requested_amount: float
    urgency: Urgency
    reason: str
    status: Literal["submitted", "approved", "denied"]
    submitted_at: str
    decided_at: Optional[str] = None
    decision_note: str = ""
    demo: bool = True


# ---------------------------------------------------------------------------
# Payment plans  (SIMULATED agreement — no real money, no e-signature)
# ---------------------------------------------------------------------------
class PaymentItem(BaseModel):
    code: str
    name: str
    cost: float


class ScheduleEntry(BaseModel):
    n: int
    due_date: str
    amount: float


class AuditEntry(BaseModel):
    at: str
    event: str


class PaymentPlanCreate(BaseModel):
    member_id: str = "demo"
    provider_id: str
    codes: list[str] = Field(min_length=1)
    term_months: int = Field(default=12, ge=1, le=60)


class PaymentPlan(BaseModel):
    id: str
    member_id: str
    member_name: str
    provider_id: str
    provider_name: str
    items: list[PaymentItem]
    total: float
    term_months: int
    monthly_amount: float
    status: Literal["draft", "sent_to_doctor", "active", "declined"]
    schedule: list[ScheduleEntry]
    audit: list[AuditEntry]
    created_at: str
    demo: bool = True


# ---------------------------------------------------------------------------
# Emergency Paid-Time-Off request  (SIMULATED HR workflow)
# ---------------------------------------------------------------------------
class PTOCreate(BaseModel):
    member_id: str = "demo"
    date_needed: str
    hours: float = Field(default=4, gt=0, le=80)
    reason: str = "Emergency dental visit"

    @field_validator("date_needed")
    @classmethod
    def _iso_date(cls, v: str) -> str:
        try:
            return date.fromisoformat(v).isoformat()
        except ValueError:
            raise ValueError("date_needed must be an ISO date (YYYY-MM-DD)")


class PTORequest(BaseModel):
    id: str
    member_id: str
    member_name: str
    employer: str
    date_needed: str
    hours: float
    reason: str
    status: Literal["submitted", "approved", "denied"]
    submitted_at: str
    decided_at: Optional[str] = None
    note: str = ""
    demo: bool = True


# ---------------------------------------------------------------------------
# Employee time-off: work schedule + PTO balance  (SIMULATED HRIS / Workday-style)
# Mock data only; no real HR system is read or written. Hours math is deterministic
# (services/pto.py) — the LLM never computes a balance.
# ---------------------------------------------------------------------------
class WorkSchedule(BaseModel):
    member_id: str
    employer: str
    timezone: str = "America/New_York"
    work_days: list[int] = [0, 1, 2, 3, 4]  # 0=Mon .. 6=Sun
    start_hour: float = Field(default=9.0, ge=0, le=24)   # 24h local time (9.0 = 9:00am)
    end_hour: float = Field(default=17.0, ge=0, le=24)
    manager: str = "Unassigned"
    source: str = "mock-hris"
    demo: bool = True

    @model_validator(mode="after")
    def _valid_window(self):
        if not all(0 <= d <= 6 for d in self.work_days):
            raise ValueError("work_days entries must be 0 (Mon) through 6 (Sun)")
        if self.end_hour <= self.start_hour:
            raise ValueError("end_hour must be after start_hour")
        return self


class WorkScheduleUpdate(BaseModel):
    """Partial update; only the fields the employee changes are sent."""
    member_id: str = "demo"
    timezone: Optional[str] = None
    work_days: Optional[list[int]] = None
    start_hour: Optional[float] = Field(default=None, ge=0, le=24)
    end_hour: Optional[float] = Field(default=None, ge=0, le=24)
    manager: Optional[str] = None

    @field_validator("work_days")
    @classmethod
    def _valid_days(cls, v):
        if v is not None and not all(0 <= d <= 6 for d in v):
            raise ValueError("work_days entries must be 0 (Mon) through 6 (Sun)")
        return sorted(set(v)) if v is not None else v


class PTOBalance(BaseModel):
    member_id: str
    employer: str
    accrued_hours: float
    used_hours: float
    pending_hours: float
    available_hours: float
    as_of: str
    source: str = "mock-hris"
    demo: bool = True


class PTOProposal(BaseModel):
    """A drafted (not submitted) time-off suggestion the agent surfaces for an in-hours emergency."""
    member_id: str
    date_needed: str
    hours: float
    reason: str
    within_work_hours: bool
    balance_available: float
    balance_after: float
    sufficient_balance: bool
    manager: str
    message: str
    demo: bool = True
