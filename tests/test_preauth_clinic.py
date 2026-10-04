from datetime import date

from schemas import PreAuthCreate
from services import clinic, preauth, tools

PLAN = tools.get_plan_details("LFG-123")


def member():
    return tools.get_member("demo").model_copy(deep=True)


def test_clinic_estimates_in_network_sorted():
    ce = clinic.clinic_estimates(member(), "P001", date(2026, 10, 1))  # in-network
    assert ce.network == "in"
    assert len(ce.services) > 0
    pays = [s.member_pays for s in ce.services]
    assert pays == sorted(pays)  # cheapest first


def test_clinic_fee_factor_changes_member_cost():
    # P004 (0.95) should be cheaper than P005 (1.18) for the same major crown
    a = {s.code: s.member_pays for s in clinic.clinic_estimates(member(), "P004", date(2026, 10, 1)).services}
    b = {s.code: s.member_pays for s in clinic.clinic_estimates(member(), "P005", date(2026, 10, 1)).services}
    assert a["D2740"] < b["D2740"]


def test_clinic_out_of_network_flagged():
    ce = clinic.clinic_estimates(member(), "P005", date(2026, 10, 1))
    assert ce.network == "out"


def test_preauth_urgent_auto_approves():
    pa = preauth.create(PreAuthCreate(member_id="demo", provider_id="P005", code="D2740",
                                      estimated_cost=1300, requested_amount=1300, urgency="urgent"))
    assert pa.status == "submitted"
    assert preauth.decide(pa.id).status == "approved"


def test_preauth_large_routine_denied_and_listed():
    pa = preauth.create(PreAuthCreate(member_id="demo", provider_id="P005", code="D2740",
                                      estimated_cost=1300, requested_amount=1300, urgency="routine"))
    assert preauth.decide(pa.id).status == "denied"
    assert any(p.id == pa.id for p in preauth.list_for("demo"))
    assert all(p.member_id == "demo" for p in preauth.list_for("demo"))
