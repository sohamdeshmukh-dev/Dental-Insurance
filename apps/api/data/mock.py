"""Mock data standing in for Lincoln plan/provider APIs and licensed cost data."""
from __future__ import annotations

from datetime import date

from schemas import (DentalPlan, FrequencyLimit, Member, Provenance, Provider,
                     ProviderNetwork, ServiceRecord, WaitingPeriod)

_src = lambda page, conf=0.99: Provenance(source_type="MOCK", source_id="lincoln-ppo-2026.pdf", page=page, confidence=conf)

PLAN = DentalPlan(
    plan_id="LFG-123", plan_name="Lincoln Dental PPO", network_type="PPO", network_id="LINCOLN_PPO",
    deductible_individual=50, annual_maximum=1500,
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

MEMBERS = {"demo": Member(
    member_id="demo", plan_id="LFG-123", zip_code="19122", coverage_effective_date=date(2024, 1, 1),
    benefits_used=550, benefits_pending=0, deductible_remaining=50,
    history=[ServiceRecord(code="D1110", service_date=date(2026, 3, 12))],
)}

PROVIDERS = [
    Provider(provider_id="P001", name="Fishtown Family Dental", specialty="General Dentist", address="1200 Frankford Ave",
             city="Philadelphia", state="PA", zip_code="19125", latitude=39.9702, longitude=-75.1340, phone="215-555-0101",
             procedures=["D0120", "D1110", "D0274", "D2391", "D2740", "D2750", "D7140", "D4341"]),
    Provider(provider_id="P002", name="Temple Endodontics", specialty="Endodontist", address="3223 N Broad St",
             city="Philadelphia", state="PA", zip_code="19140", latitude=40.0100, longitude=-75.1530, phone="215-555-0102",
             procedures=["D3310", "D3320", "D3330"]),
    Provider(provider_id="P003", name="Girard Smile Studio", specialty="General Dentist", address="1500 W Girard Ave",
             city="Philadelphia", state="PA", zip_code="19130", latitude=39.9700, longitude=-75.1650, phone="215-555-0103",
             procedures=["D0120", "D1110", "D2391", "D2740", "D3310", "D3320", "D3330"]),
    Provider(provider_id="P004", name="Northern Liberties Dental", specialty="General Dentist", address="900 N 2nd St",
             city="Philadelphia", state="PA", zip_code="19123", latitude=39.9640, longitude=-75.1400, phone="215-555-0104",
             procedures=["D0120", "D1110", "D2740", "D4341", "D3330"]),
    Provider(provider_id="P005", name="Center City Premier Dentistry", specialty="General Dentist", address="1800 Walnut St",
             city="Philadelphia", state="PA", zip_code="19103", latitude=39.9500, longitude=-75.1720, phone="215-555-0105",
             procedures=["D0120", "D1110", "D2740", "D3330"]),
    Provider(provider_id="P006", name="Kensington Endodontic Care", specialty="Endodontist", address="2500 E Allegheny Ave",
             city="Philadelphia", state="PA", zip_code="19134", latitude=39.9860, longitude=-75.1000, phone="215-555-0106",
             procedures=["D3310", "D3320", "D3330"]),
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
