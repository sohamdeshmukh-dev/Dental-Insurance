"""Background research briefs: queued only when a procedure was identified, run exactly once via
a claim, and every fact in the brief still comes from the deterministic tools (scripted fake
``converse``, no AWS)."""
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

import main
from services import brief_store, research, tools
from test_bedrock_agent import FakeConverse, _final as final, _tool_use as tool_use

PRICED = {"procedures": [{"selected_code": "D3330"}]}


@pytest.fixture(autouse=True)
def memory_store(monkeypatch):
    monkeypatch.delenv("BRIEFS_TABLE", raising=False)
    brief_store._MEMORY.clear()


def test_codes_from_both_engine_shapes():
    assert research.codes_from(PRICED) == ["D3330"]
    assert research.codes_from({"tool_calls": [
        {"tool": "compare_networks", "input": {"code": "D2740"}, "status": "success"},
        {"tool": "compare_networks", "input": {"code": "NOPE"}, "status": "error"},
        {"tool": "get_benefit_usage", "input": {}, "status": "success"},
    ]}) == ["D2740"]
    assert research.codes_from({"status": "OK", "explanation": "Hello!"}) == []


def test_queue_only_when_procedure_session_and_bedrock(monkeypatch):
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    assert research.queue("s1", PRICED, "root canal", None) is False  # no model configured

    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    assert research.queue(None, PRICED, "hi", None) is False                    # no session
    assert research.queue("s1", {"explanation": "Hello!"}, "hi", None) is False  # nothing priced

    assert research.queue("s1", PRICED, "root canal", date(2026, 10, 1)) is True
    stored = brief_store.get("s1")
    assert (stored["status"], stored["codes"], stored["today"]) == ("PENDING", ["D3330"], "2026-10-01")
    # the run request never arrived, so the same question re-queues instead of being lost
    assert research.queue("s1", PRICED, "root canal", None) is True
    brief_store.claim("s1")
    assert research.queue("s1", PRICED, "root canal", None) is False  # RUNNING: don't pay twice


def test_claim_is_exclusive_and_stale_running_is_recoverable(monkeypatch):
    assert brief_store.claim("none") is False  # nothing queued
    brief_store.put("s1", {"status": "PENDING", "codes": ["D3330"]})
    assert brief_store.claim("s1") is True
    assert brief_store.claim("s1") is False  # someone else is running it
    brief_store._MEMORY["s1"]["updated_at"] -= brief_store.STALE_SECONDS + 1
    assert brief_store.claim("s1") is True   # crashed job gets retried
    brief_store.put("s1", {"status": "READY", "codes": ["D3330"]})
    assert brief_store.claim("s1") is False  # done


def test_run_pending_stores_brief_built_from_tool_results(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    research.queue("s1", PRICED, "I need a root canal", date(2026, 10, 1))
    fake = FakeConverse([tool_use("compare_networks", {"code": "D3330"}),
                         tool_use("get_benefit_usage", {}),
                         final("Your root canal fits within your remaining annual maximum.")])

    research.run_pending("s1", converse=fake)

    brief = brief_store.get("s1")
    assert brief["status"] == "READY" and brief["codes"] == ["D3330"]
    assert brief["procedures"] == [tools.lookup_procedure("D3330").name]
    assert [c["tool"] for c in brief["tool_calls"]] == ["compare_networks", "get_benefit_usage"]
    assert "actual benefits are determined when the claim is processed" in brief["disclaimer"]
    assert "D3330" in fake.calls[0]["messages"][0]["content"][0]["text"]
    assert "2026-10-01" in fake.calls[0]["system"][0]["text"]  # the queued date reaches the agent

    again = FakeConverse([])  # a second run must not call the model at all
    assert research.run_pending("s1", converse=again)["status"] == "READY" and not again.calls


def test_run_pending_records_failure(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    research.queue("s2", PRICED, "root canal", None)

    def boom(**_):
        raise RuntimeError("throttled")

    research.run_pending("s2", converse=boom)
    assert brief_store.get("s2")["status"] == "FAILED"
    assert brief_store.get("s2")["error"] == "throttled"
    assert research.queue("s2", PRICED, "root canal", None) is True  # FAILED gets another go


def test_endpoints_end_to_end(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setattr(main.bedrock_agent, "run", lambda message, **kw: (
        {"status": "OK", "engine": "bedrock", "explanation": "ok", "tool_calls": [
            {"tool": "compare_networks", "input": {"code": "D3330"}, "status": "success"}], "trace": []}
        if "Earlier they wrote" not in message else
        {"explanation": "the brief", "tool_calls": [], "trace": []}))
    client = TestClient(main.app)

    chat = client.post("/api/v1/agent/message", json={"message": "root canal", "session_id": "s9"}).json()
    assert chat["research_pending"] is True
    assert client.get("/api/v1/research/s9").json()["status"] == "PENDING"

    assert client.post("/api/v1/research/s9/run").json() == {"status": "READY"}
    assert client.post("/api/v1/research/s9/run").json() == {"status": "READY"}  # idempotent
    assert client.get("/api/v1/research/s9").json()["brief"] == "the brief"
    assert client.get("/api/v1/research/nobody").json() == {"status": "NONE"}


class FakeDynamo:
    """Just enough of the DynamoDB client to check what the store sends."""

    def __init__(self):
        self.items, self.calls = {}, []

    def put_item(self, **kw):
        self.calls.append(("put_item", kw))
        self.items[kw["Item"]["session_id"]["S"]] = kw["Item"]

    def get_item(self, **kw):
        self.calls.append(("get_item", kw))
        item = self.items.get(kw["Key"]["session_id"]["S"])
        return {"Item": item} if item else {}

    def update_item(self, **kw):
        self.calls.append(("update_item", kw))
        item = self.items[kw["Key"]["session_id"]["S"]]
        if item["status"]["S"] != "PENDING":
            err = Exception("conditional check failed")
            err.response = {"Error": {"Code": "ConditionalCheckFailedException"}}
            raise err
        item["status"] = kw["ExpressionAttributeValues"][":running"]


def test_dynamodb_backend(monkeypatch):
    fake = FakeDynamo()
    monkeypatch.setenv("BRIEFS_TABLE", "briefs")
    monkeypatch.setattr(brief_store, "_client", fake)

    # floats (latencies) must survive: the brief is stored as one JSON string
    brief_store.put("s1", {"status": "PENDING", "codes": ["D3330"], "trace": [{"latency_ms": 1.5}]})
    put = fake.items["s1"]
    assert json.loads(put["data"]["S"])["trace"][0]["latency_ms"] == 1.5
    assert float(put["expires_at"]["N"]) > float(put["updated_at"]["N"])  # TTL attribute is set

    assert brief_store.claim("s1") is True
    assert brief_store.claim("s1") is False  # ConditionalCheckFailed -> someone else owns it
    update = [kw for name, kw in fake.calls if name == "update_item"][0]
    assert "#s = :pending" in update["ConditionExpression"]
    assert brief_store.get("s1")["status"] == "RUNNING"  # status attribute overlays the JSON
    assert brief_store.get("missing") is None


def test_chat_survives_a_broken_brief_store(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    monkeypatch.setattr(main.bedrock_agent, "run", lambda message, **kw: {
        "status": "OK", "engine": "bedrock", "explanation": "your estimate", "tool_calls": [
            {"tool": "compare_networks", "input": {"code": "D3330"}, "status": "success"}], "trace": []})

    def broken(*_a, **_k):
        raise RuntimeError("table not found")

    monkeypatch.setattr(brief_store, "get", broken)
    out = TestClient(main.app).post("/api/v1/agent/message", json={"message": "root canal", "session_id": "s1"})
    assert out.status_code == 200
    body = out.json()
    assert body["explanation"] == "your estimate"
    assert body["research_pending"] is False and body["research_error"] == "RuntimeError"
