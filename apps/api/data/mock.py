"""Mock data standing in for Lincoln plan/provider APIs and licensed cost data."""
from __future__ import annotations

from datetime import date

from schemas import (DentalPlan, FrequencyLimit, Member, PaidClaim, Provenance, Provider,
                     ProviderNetwork, ServiceRecord, WaitingPeriod)

_src = lambda page, conf=0.99: Provenance(source_type="MOCK", source_id="lincoln-ppo-2026.pdf", page=page, confidence=conf)

PLAN = DentalPlan(
    plan_id="LFG-123", plan_name="Lincoln Dental PPO", network_type="PPO", network_id="LINCOLN_PPO",
    deductible_individual=50, annual_maximum=2000,
    coinsurance_in_network={"preventive": 1.0, "basic": 0.8, "major": 0.5, "ortho": 0.5},
    coinsurance_out_of_network={"preventive": 0.8, "basic": 0.6, "major": 0.4, "ortho": 0.4},
    plan_year_start=date(2026, 1, 1), plan_year_end=date(2026, 12, 31),
    waiting_periods=[WaitingPeriod(category="major", months=6)],
    exclusions=[],
    frequency_limits=[FrequencyLimit(codes=["D1110"], count=2, period_months=12),
                      FrequencyLimit(codes=["D0274"], count=1, period_months=12)],
    provenance={
        "annual_maximum": _src(4), "deductible_individual": _src(4),
        "coinsurance_in_network.preventive": _src(6), "coinsurance_in_network.basic": _src(6),
        "coinsurance_in_network.major": _src(7), "coinsurance_out_of_network": _src(7),
        "waiting_periods": _src(8), "frequency_limits": _src(9),
    },
)

# Paid claims so far this plan year (plan_paid sums to benefits_used = 550).
_CLAIMS = [
    PaidClaim(service_date=date(2026, 2, 18), code="D0120", description="Periodic oral exam",
              category="preventive", plan_paid=55, member_paid=0),
    PaidClaim(service_date=date(2026, 2, 18), code="D0274", description="Bitewing X-rays (4 films)",
              category="preventive", plan_paid=70, member_paid=0),
    PaidClaim(service_date=date(2026, 3, 12), code="D1110", description="Adult cleaning",
              category="preventive", plan_paid=90, member_paid=0),
    PaidClaim(service_date=date(2026, 5, 20), code="D2391", description="Resin filling (1 surface)",
              category="basic", plan_paid=120, member_paid=30),
    PaidClaim(service_date=date(2026, 8, 7), code="D2391", description="Resin filling (1 surface)",
              category="basic", plan_paid=120, member_paid=30),
    PaidClaim(service_date=date(2026, 8, 7), code="D1110", description="Adult cleaning",
              category="preventive", plan_paid=95, member_paid=0),
]

# Dependent (child) paid claims — pediatric preventive care this plan year.
_CHILD_CLAIMS = [
    PaidClaim(service_date=date(2026, 4, 3), code="D0120", description="Periodic oral exam (child)",
              category="preventive", plan_paid=50, member_paid=0),
    PaidClaim(service_date=date(2026, 4, 3), code="D1206", description="Fluoride treatment",
              category="preventive", plan_paid=40, member_paid=0),
    PaidClaim(service_date=date(2026, 4, 3), code="D1110", description="Child cleaning",
              category="preventive", plan_paid=85, member_paid=0),
    PaidClaim(service_date=date(2026, 9, 15), code="D1351", description="Sealant, permanent molar",
              category="preventive", plan_paid=45, member_paid=0),
]


def _member(mid, name, rel, claims, *, age=None, deductible_remaining=50):
    return Member(
        member_id=mid, plan_id="LFG-123", zip_code="19122", coverage_effective_date=date(2024, 1, 1),
        name=name, relationship=rel, age=age,
        benefits_used=sum(c.plan_paid for c in claims), benefits_pending=0, deductible_remaining=deductible_remaining,
        history=[ServiceRecord(code=c.code, service_date=c.service_date) for c in claims], claims=claims)


MEMBERS = {
    "demo": _member("demo", "Jordan Lee", "guardian", _CLAIMS),
    "demo-child": _member("demo-child", "Riley Lee", "dependent", _CHILD_CLAIMS, age=9, deductible_remaining=0),
}

ACCOUNT = {"account_id": "ACME-0007", "employer": "Acme Co", "guardian_id": "demo",
           "member_ids": ["demo", "demo-child"]}

PROVIDERS = [
    Provider(provider_id="P001", name="Fishtown Family Dental", specialty="General Dentist", address="1200 Frankford Ave",
             city="Philadelphia", state="PA", zip_code="19125", latitude=39.9702, longitude=-75.1340, phone="215-555-0101",
             procedures=["D0120", "D1110", "D0274", "D2391", "D2740", "D2750", "D7140", "D4341"], fee_factor=0.98),
    Provider(provider_id="P002", name="Temple Endodontics", specialty="Endodontist", address="3223 N Broad St",
             city="Philadelphia", state="PA", zip_code="19140", latitude=40.0100, longitude=-75.1530, phone="215-555-0102",
             procedures=["D3310", "D3320", "D3330"], fee_factor=1.08),
    Provider(provider_id="P003", name="Girard Smile Studio", specialty="General Dentist", address="1500 W Girard Ave",
             city="Philadelphia", state="PA", zip_code="19130", latitude=39.9700, longitude=-75.1650, phone="215-555-0103",
             procedures=["D0120", "D1110", "D2391", "D2740", "D3310", "D3320", "D3330"], fee_factor=1.0),
    Provider(provider_id="P004", name="Northern Liberties Dental", specialty="General Dentist", address="900 N 2nd St",
             city="Philadelphia", state="PA", zip_code="19123", latitude=39.9640, longitude=-75.1400, phone="215-555-0104",
             procedures=["D0120", "D1110", "D2740", "D4341", "D3330"], fee_factor=0.95),
    Provider(provider_id="P005", name="Center City Premier Dentistry", specialty="General Dentist", address="1800 Walnut St",
             city="Philadelphia", state="PA", zip_code="19103", latitude=39.9500, longitude=-75.1720, phone="215-555-0105",
             procedures=["D0120", "D1110", "D2740", "D3330"], fee_factor=1.18),
    Provider(provider_id="P006", name="Kensington Endodontic Care", specialty="Endodontist", address="2500 E Allegheny Ave",
             city="Philadelphia", state="PA", zip_code="19134", latitude=39.9860, longitude=-75.1000, phone="215-555-0106",
             procedures=["D3310", "D3320", "D3330"], fee_factor=1.1),
]

NETWORKS = [ProviderNetwork(provider_id=pid, network_id="LINCOLN_PPO", effective_date=date(2023, 1, 1),
                            verification_timestamp="2026-09-15T00:00:00Z", source="mock-lincoln-directory")
            for pid in ("P001", "P002", "P003", "P004", "P006")]
# P005 intentionally has no membership (out of network); P006's contract has lapsed:
NETWORKS[-1].termination_date = date(2026, 6, 30)

ZIP_CENTROIDS = {
    "19122": (39.9780, -75.1370), "19103": (39.9526, -75.1745), "19104": (39.9570, -75.1980),
    "19125": (39.9700, -75.1250), "19146": (39.9370, -75.1830),
}

# Mock "FAIR Health" style data: base in-network allowed fee and typical billed charge ratio.
BASE_FEES = {
    "D0120": 55, "D0274": 70, "D1110": 110, "D4341": 260, "D4342": 180, "D2391": 190, "D7140": 175,
    "D3310": 700, "D3320": 850, "D3330": 850, "D2740": 1100, "D2750": 1050,
}
ZIP_FACTORS = {"191": 1.0}  # prefix -> regional factor
