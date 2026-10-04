"""Tests for the Bedrock Converse tool-use orchestrator.

A scripted fake ``converse`` stands in for AWS so the full tool loop is exercised with no
network, no credentials, and no boto3 install. The key guarantee under test: every benefit
number the agent reports comes from the deterministic engine via a tool result, never the model.
"""
from datetime import date

from services import bedrock_agent


import copy


class FakeConverse:
    """Replays a scripted sequence of Bedrock Converse responses and records what it was sent.

    The orchestrator mutates the ``messages`` list in place across turns, so we snapshot a deep
    copy of each call's kwargs to capture the state at call time rather than the final state.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        return self._responses.pop(0)


def _tool_use(name, args, tool_use_id="t1"):
    return {"output": {"message": {"role": "assistant",
            "content": [{"toolUse": {"name": name, "input": args, "toolUseId": tool_use_id}}]}},
            "stopReason": "tool_use"}


def _final(text):
    return {"output": {"message": {"role": "assistant", "content": [{"text": text}]}},
            "stopReason": "end_turn"}


def test_bedrock_enabled_follows_env(monkeypatch):
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    assert bedrock_agent.bedrock_enabled() is False
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
    assert bedrock_agent.bedrock_enabled() is True


def test_tool_loop_runs_deterministic_tools(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    # Script: interpret -> compare coverage -> find offices -> final narrative.
    fake = FakeConverse([
        _tool_use("interpret_procedure", {"text": "root canal on tooth 14", "tooth": 14}),
        _tool_use("compare_networks", {"code": "D3330"}),
        _tool_use("search_network_providers", {"zip_code": "19122", "procedure": "D3330"}),
        _final("Here is your root canal estimate and nearby in-network offices."),
    ])

    out = bedrock_agent.run("I need a root canal on tooth 14, I live near 19122.",
                            today=date(2026, 10, 1), converse=fake)

    assert out["engine"] == "bedrock"
    assert out["status"] == "OK"
    assert out["explanation"].startswith("Here is your root canal")

    names = [c["tool"] for c in out["tool_calls"]]
    assert names == ["interpret_procedure", "compare_networks", "search_network_providers"]
    assert all(c["status"] == "success" for c in out["tool_calls"])

    # The provider result the model received must carry a verified network status from the
    # engine (not something the model asserted on its own).
    search_call = fake.calls[-1]  # last converse call carried the search toolResult back
    tool_result = search_call["messages"][-1]["content"][0]["toolResult"]
    providers = tool_result["content"][0]["json"]["providers"]
    assert providers and providers[0]["network_status"] == "VERIFIED_IN_NETWORK"

    # The trace records a span per converse turn plus a span per tool call.
    assert sum(1 for e in out["trace"] if e["tool"] == "converse") == 4
    assert {e["tool"] for e in out["trace"]} >= {
        "converse", "interpret_procedure", "compare_networks", "search_network_providers"}


def test_tool_errors_are_returned_to_model_not_raised(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    fake = FakeConverse([
        _tool_use("compare_networks", {"code": "NOPE"}),  # unknown code -> engine raises
        _final("I couldn't find coverage for that code."),
    ])
    out = bedrock_agent.run("coverage for NOPE?", today=date(2026, 10, 1), converse=fake)
    assert out["tool_calls"][0]["status"] == "error"
    # The error was passed back to the model as a toolResult, and the loop finished cleanly.
    err_payload = fake.calls[1]["messages"][-1]["content"][0]["toolResult"]["content"][0]["json"]
    assert "error" in err_payload
    assert out["status"] == "OK"


def test_loop_is_bounded(monkeypatch):
    monkeypatch.setenv("BEDROCK_MODEL_ID", "test-model")
    # Always ask for a tool, never stop — the loop must terminate at MAX_TURNS.
    always_tool = [_tool_use("get_benefit_usage", {}) for _ in range(bedrock_agent.MAX_TURNS + 5)]
    fake = FakeConverse(always_tool)
    out = bedrock_agent.run("usage?", today=date(2026, 10, 1), converse=fake)
    assert len(fake.calls) == bedrock_agent.MAX_TURNS
    assert out["explanation"]  # a fallback message is produced
