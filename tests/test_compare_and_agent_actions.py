"""Phase 2/3 tests: side-by-side in/out service comparison, and the conversational agent
tools for payment plans and out-of-network pre-authorization (Bedrock Converse loop)."""
from datetime import date

from fastapi.testclient import TestClient

from main import app
from services import bedrock_agent
from test_bedrock_agent import FakeConverse, _final, _tool_use

client = TestClient(app)


# --- Phase 2: compare selected services, in vs out ----------------------------------------
def test_compare_services_endpoint():
    r = client.post("/api/v1/benefits/compare", json={"member_id": "demo", "codes": ["D2740", "D1110"]})
    assert r.status_code == 200
    body = r.json()
    assert {row["code"] for row in body["rows"]} == {"D2740", "D1110"}
    assert body["in_total"] <= body["out_total"]
    assert round(body["out_total"] - body["in_total"], 2) == body["savings_total"]
    assert "actual" in body["disclaimer"].lower()


def test_compare_services_validation():
    assert client.post("/api/v1/benefits/compare", json={"codes": []}).status_code == 422
    assert client.post("/api/v1/benefits/compare", json={"codes": ["D9999"]}).status_code == 404


# --- Phase 3: agent-driven payment plan & pre-auth (numbers come from tools) ---------------
def test_agent_can_draft_and_send_payment_plan(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    fake = FakeConverse([
        _tool_use("create_payment_plan", {"provider_id": "P001", "codes": ["D2740"], "term_months": 6}),
        _tool_use("send_payment_plan_to_dentist", {"plan_id": "PP-0001"}, tool_use_id="t2"),
        _final("I drafted a 6-month plan and sent it to the dentist for approval (simulated)."),
    ])
    out = bedrock_agent.run("set up a payment plan for my crown at Fishtown", converse=fake)
    calls = [c["tool"] for c in out["tool_calls"]]
    assert calls == ["create_payment_plan", "send_payment_plan_to_dentist"]
    assert all(c["status"] == "success" for c in out["tool_calls"])


def test_agent_preauth_amount_comes_from_engine(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    # The model supplies no dollar amount; the tool derives it from the coverage engine.
    fake = FakeConverse([
        _tool_use("create_preauth", {"provider_id": "P005", "code": "D2740", "urgency": "urgent"}),
        _final("Your pre-authorization was submitted to Lincoln Financial (simulated)."),
    ])
    out = bedrock_agent.run("request pre-authorization at the out-of-network office", converse=fake)
    assert out["tool_calls"][0]["tool"] == "create_preauth" and out["tool_calls"][0]["status"] == "success"
    from services import preauth
    latest = preauth.list_for("demo")[0]
    assert latest.status == "submitted" and latest.requested_amount > 0 and latest.provider_id == "P005"


def test_agent_compare_services_tool(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    fake = FakeConverse([
        _tool_use("compare_services", {"codes": ["D2740"]}),
        _final("In-network you'd pay less than out-of-network for the crown."),
    ])
    out = bedrock_agent.run("compare a crown in vs out of network", converse=fake)
    assert out["tool_calls"][0]["tool"] == "compare_services"
    assert out["unverified_figures"] == []
