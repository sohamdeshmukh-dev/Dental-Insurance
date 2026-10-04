from __future__ import annotations

import logging
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from schemas import (AgentMessage, CarePlanRequest, EstimateRequest, InterpretRequest, RedeemRequest)
from services import bedrock_agent, brief_store
from services import research
from services import rewards as rewards_svc
from services import tools
from services.procedures import interpret
from services.supervisor import compare_networks, run

app = FastAPI(title="Dental Benefits Optimizer API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MEMBER_ID = "demo"


@app.get("/health")
def health():
    return {"status": "ok", "calculation_version": tools.coverage.CALC_VERSION}


@app.post("/api/v1/procedures/interpret")
def interpret_procedure(req: InterpretRequest):
    return {"matches": [m.model_dump() for m in interpret(req.text)]}


@app.post("/api/v1/benefits/estimate")
def estimate(req: EstimateRequest):
    try:
        plan = tools.get_plan_details(req.plan_id)
        member = tools.get_member(MEMBER_ID)
        both = compare_networks(plan, member, req.procedure_code, date.today())
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"in_network": both["in"].model_dump(), "out_of_network": both["out"].model_dump()}


@app.get("/api/v1/providers")
def get_providers(zip_code: str = Query("19122"), radius: float = 10, procedure: str | None = None,
                  specialty: str | None = None, include_out_of_network: bool = False):
    plan = tools.get_plan_details("LFG-123")
    try:
        results = tools.search_network_providers(plan, zip_code, date.today(), radius=radius, procedure=procedure,
                                                 specialty=specialty, include_out_of_network=include_out_of_network)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"providers": [r.model_dump() for r in results]}


@app.get("/api/v1/benefits/usage")
def usage():
    plan = tools.get_plan_details("LFG-123")
    member = tools.get_member(MEMBER_ID)
    return tools.get_benefit_usage(plan, member).model_dump()


@app.post("/api/v1/care-plan/optimize")
def care_plan(req: CarePlanRequest):
    plan = tools.get_plan_details("LFG-123")
    member = tools.get_member(MEMBER_ID)
    try:
        cp = tools.optimize_treatment_sequence(plan, member, req.codes, set(req.urgent_codes), req.network,
                                               req.today or date.today())
    except KeyError as e:
        raise HTTPException(404, f"Unknown procedure code {e}")
    return cp.model_dump()


@app.post("/api/v1/agent/message")
def agent_message(req: AgentMessage):
    # When a Bedrock model is configured (BEDROCK_MODEL_ID), use the Converse tool-use
    # orchestrator; otherwise fall back to the deterministic rule-based supervisor. If the
    # Bedrock call fails at runtime, degrade gracefully to the supervisor rather than erroring.
    if bedrock_agent.bedrock_enabled():
        try:
            result = bedrock_agent.run(req.message, today=req.today, session_id=req.session_id)
        except Exception as exc:  # pragma: no cover - exercised only with a live/broken AWS config
            result = run(req.message, today=req.today, session_id=req.session_id)
            result["engine"] = "supervisor"
            result["bedrock_error"] = str(exc)
        # Once a procedure is identified, record a brief to research; the page then calls
        # POST /research/{session_id}/run (serverless can't run work after the response).
        try:
            result["research_pending"] = research.queue(req.session_id, result, req.message, req.today)
        except Exception as exc:  # the brief store is optional; never fail the reply over it
            logging.exception("research queue failed")
            result["research_pending"] = False
            result["research_error"] = type(exc).__name__
        return result
    result = run(req.message, today=req.today, session_id=req.session_id)
    result["engine"] = "supervisor"
    return result


@app.get("/api/v1/research/{session_id}")
def research_brief(session_id: str):
    return brief_store.get(session_id) or {"status": "NONE"}


@app.post("/api/v1/research/{session_id}/run")
def research_run(session_id: str):
    # Runs the queued brief inside this request (~30-45s). Safe to call twice: only the caller
    # that wins the claim does the work.
    return {"status": research.run_pending(session_id)["status"]}


@app.get("/api/v1/benefits/timeline")
def benefits_timeline():
    plan = tools.get_plan_details("LFG-123")
    member = tools.get_member(MEMBER_ID)
    return tools.get_funding_timeline(plan, member, date.today()).model_dump()


@app.get("/api/v1/rewards")
def rewards():
    plan = tools.get_plan_details("LFG-123")
    member = tools.get_member(MEMBER_ID)
    return tools.get_rewards(plan, member).model_dump()


@app.post("/api/v1/rewards/redeem")
def rewards_redeem(req: RedeemRequest):
    plan = tools.get_plan_details("LFG-123")
    member = tools.get_member(MEMBER_ID)
    profile = tools.get_rewards(plan, member)
    ok, msg, bal, entries = rewards_svc.redeem(profile, req.item_id)
    return {"ok": ok, "message": msg, "points_balance": bal, "sweepstakes_entries": entries}
