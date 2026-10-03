from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from schemas import (AgentMessage, CarePlanRequest, EstimateRequest, InterpretRequest)
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
    return run(req.message, today=req.today, session_id=req.session_id)
