"""Regression tests for the code-review fixes (validation, guardrails, output verification)."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from schemas import PaymentPlanCreate, PreAuthCreate, PTOCreate
from services import bedrock_agent
from services.guardrails import collect_facts, screen_input
from test_bedrock_agent import FakeConverse, _final, _tool_use

client = TestClient(app)


def test_estimate_unknown_code_is_404():
    r = client.post("/api/v1/benefits/estimate", json={"plan_id": "LFG-123", "procedure_code": "D9999"})
    assert r.status_code == 404


def test_payment_plan_rejects_unknown_empty_and_unoffered_codes():
    assert client.post("/api/v1/payment-plans", json={"provider_id": "P001", "codes": []}).status_code == 422
    assert client.post("/api/v1/payment-plans", json={"provider_id": "P001", "codes": ["D9999"]}).status_code == 404
    from services import procedures
    from services.providers import get_provider
    unoffered = next(c for c in procedures.CATALOG if c not in get_provider("P001").procedures)
    assert client.post("/api/v1/payment-plans", json={"provider_id": "P001", "codes": [unoffered]}).status_code == 400


@pytest.mark.parametrize("text", ["How much is a cleaning?", "Are fillings covered?", "Do you cover braces?"])
def test_plural_and_gerund_dental_terms_are_on_topic(text):
    assert screen_input(text).ok


@pytest.mark.parametrize("text", ["yes", "19122", "ok", "$500"])
def test_short_followups_pass(text):
    assert screen_input(text).ok


def test_off_topic_still_redirected():
    assert not screen_input("what's the weather like in Paris").ok


@pytest.mark.parametrize("text", ["my swelling is spreading", "the swelling and spreading toward my eye", "jaw swelling"])
def test_red_flag_variants(text):
    assert screen_input(text).urgent


def test_preauth_rejects_negative_amounts():
    with pytest.raises(ValidationError):
        PreAuthCreate(provider_id="P001", code="D2740", estimated_cost=100, requested_amount=-5)


def test_lists_validate_member():
    for path in ("preauth", "payment-plans", "pto"):
        assert client.get(f"/api/v1/{path}?member_id=nobody").status_code == 404


def test_decide_checks_owner():
    pa = client.post("/api/v1/preauth", json={"provider_id": "P001", "code": "D2740",
                                              "estimated_cost": 900, "requested_amount": 900}).json()
    assert client.post(f"/api/v1/preauth/{pa['id']}/decide?member_id=someone-else").status_code == 404
    assert client.post(f"/api/v1/preauth/{pa['id']}/decide?member_id=demo").status_code == 200


def test_pto_and_term_validation():
    for bad in ({"date_needed": "tomorrow"}, {"date_needed": "2026-10-05", "hours": -3},
                {"date_needed": "2026-10-05", "hours": 0}):
        with pytest.raises(ValidationError):
            PTOCreate(**bad)
    for term in (0, 61):
        with pytest.raises(ValidationError):
            PaymentPlanCreate(provider_id="P001", codes=["D2740"], term_months=term)


def test_collect_facts_keeps_percent_used():
    amounts, pcts = set(), set()
    collect_facts({"percent_used": 40, "coinsurance": 0.2, "annual": {"spent": 612.4}}, amounts, pcts)
    assert {40, 20} <= pcts and 612 in amounts


def test_live_agent_flags_unverified_figures(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    fake = FakeConverse([_final("That will cost only $12 out of pocket.")])
    out = bedrock_agent.run("how much is a crown?", converse=fake)
    assert "$12" in out["unverified_figures"] and "couldn't be verified" in out["explanation"]
    fake = FakeConverse([_tool_use("compare_networks", {"code": "D2740"}), _final("ok")])
    assert bedrock_agent.run("crown", converse=fake)["unverified_figures"] == []
