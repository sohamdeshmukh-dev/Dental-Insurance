from __future__ import annotations

from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from schemas import (AgentMessage, CarePlanRequest, EstimateRequest, InterpretRequest, PaymentPlanCreate,
                     PreAuthCreate, PTOCreate, RedeemRequest)
from services import bedrock_agent, brief_store
from services import payment_plans as pp_svc
from services import preauth as preauth_svc
from services import pto as pto_svc
from services import research
from services import rewards as rewards_svc
from services import tools
from services.procedures import interpret
from services.supervisor import compare_networks, run

app = FastAPI(title="Dental Benefits Optimizer API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def member_of(member_id: str):
    try:
        return tools.get_member(member_id)
    except KeyError:
        raise HTTPException(404, f"Unknown member {member_id}")


@app.get("/health")
def health():
    return {"status": "ok", "calculation_version": tools.coverage.CALC_VERSION}


@app.get("/api/v1/account")
def account():
    return tools.get_account().model_dump()


@app.post("/api/v1/procedures/interpret")
def interpret_procedure(req: InterpretRequest):
    return {"matches": [m.model_dump() for m in interpret(req.text)]}


@app.post("/api/v1/benefits/estimate")
def estimate(req: EstimateRequest):
    try:
        plan = tools.get_plan_details(req.plan_id)
    except KeyError as e:
        raise HTTPException(404, str(e))
    member = member_of(req.member_id)
    both = compare_networks(plan, member, req.procedure_code, date.today())
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
def usage(member_id: str = Query("demo")):
    plan = tools.get_plan_details("LFG-123")
    return tools.get_benefit_usage(plan, member_of(member_id)).model_dump()


@app.get("/api/v1/benefits/timeline")
def benefits_timeline(member_id: str = Query("demo")):
    plan = tools.get_plan_details("LFG-123")
    return tools.get_funding_timeline(plan, member_of(member_id), date.today()).model_dump()


@app.post("/api/v1/care-plan/optimize")
def care_plan(req: CarePlanRequest):
    plan = tools.get_plan_details("LFG-123")
    member = member_of(req.member_id)
    try:
        cp = tools.optimize_treatment_sequence(plan, member, req.codes, set(req.urgent_codes), req.network,
                                               req.today or date.today())
    except KeyError as e:
        raise HTTPException(404, f"Unknown procedure code {e}")
    return cp.model_dump()


@app.post("/api/v1/agent/message")
def agent_message(req: AgentMessage):
    # Guardrails first: emergencies, PII, off-topic (clinical urgency before finances).
    member_of(req.member_id)
    from services.guardrails import screen_input
    screen = screen_input(req.message)
    if screen.urgent:
        return {"status": "EMERGENCY", "message": screen.message, "urgent": True, "via": "guardrail"}
    if not screen.ok:
        return {"status": "NEEDS_INFORMATION", "message": screen.message, "via": "guardrail"}
    # When a Bedrock model is configured (BEDROCK_MODEL_ID), use the Converse tool-use
    # orchestrator; otherwise fall back to the deterministic rule-based supervisor. If the
    # Bedrock call fails at runtime, degrade gracefully to the supervisor rather than erroring.
    if bedrock_agent.bedrock_enabled():
        try:
            result = bedrock_agent.run(screen.text, member_id=req.member_id, today=req.today, session_id=req.session_id)
        except Exception as exc:  # pragma: no cover - exercised only with a live/broken AWS config
            result = run(req.message, member_id=req.member_id, today=req.today, session_id=req.session_id)
            result["engine"] = "supervisor"
            result["bedrock_error"] = str(exc)
        # Once a procedure is identified, record a brief to research; the page then calls
        # POST /research/{session_id}/run (serverless can't run work after the response).
        result["research_pending"] = research.queue(req.session_id, result, req.message, req.today)
        return result
    result = run(req.message, member_id=req.member_id, today=req.today, session_id=req.session_id)
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


@app.get("/api/v1/rewards")
def rewards(member_id: str = Query("demo")):
    plan = tools.get_plan_details("LFG-123")
    return tools.get_rewards(plan, member_of(member_id)).model_dump()


@app.post("/api/v1/rewards/redeem")
def rewards_redeem(req: RedeemRequest):
    plan = tools.get_plan_details("LFG-123")
    profile = tools.get_rewards(plan, member_of(req.member_id))
    ok, msg, bal, entries = rewards_svc.redeem(profile, req.item_id)
    return {"ok": ok, "message": msg, "points_balance": bal, "sweepstakes_entries": entries}


@app.get("/api/v1/providers/{provider_id}/estimates")
def clinic_estimates(provider_id: str, member_id: str = Query("demo")):
    try:
        return tools.get_clinic_estimates(member_of(member_id), provider_id, date.today()).model_dump()
    except KeyError:
        raise HTTPException(404, f"Unknown provider {provider_id}")


@app.post("/api/v1/preauth")
def preauth_create(req: PreAuthCreate):
    member_of(req.member_id)
    try:
        return preauth_svc.create(req).model_dump()
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/v1/preauth")
def preauth_list(member_id: str = Query("demo")):
    return {"requests": [p.model_dump() for p in preauth_svc.list_for(member_id)]}


@app.post("/api/v1/preauth/{pa_id}/decide")
def preauth_decide(pa_id: str):
    try:
        return preauth_svc.decide(pa_id).model_dump()
    except KeyError:
        raise HTTPException(404, f"Unknown pre-auth {pa_id}")


@app.post("/api/v1/payment-plans")
def payment_plan_create(req: PaymentPlanCreate):
    member_of(req.member_id)
    try:
        return pp_svc.create(req).model_dump()
    except KeyError as e:
        raise HTTPException(404, str(e))


@app.get("/api/v1/payment-plans")
def payment_plan_list(member_id: str = Query("demo")):
    return {"plans": [p.model_dump() for p in pp_svc.list_for(member_id)]}


@app.post("/api/v1/payment-plans/{pp_id}/send")
def payment_plan_send(pp_id: str):
    try:
        return pp_svc.send_to_doctor(pp_id).model_dump()
    except KeyError:
        raise HTTPException(404, f"Unknown plan {pp_id}")


@app.post("/api/v1/payment-plans/{pp_id}/doctor-decision")
def payment_plan_decision(pp_id: str, approve: bool = Query(True)):
    try:
        return pp_svc.doctor_decision(pp_id, approve).model_dump()
    except KeyError:
        raise HTTPException(404, f"Unknown plan {pp_id}")


@app.post("/api/v1/pto")
def pto_create(req: PTOCreate):
    member_of(req.member_id)
    return pto_svc.create(req).model_dump()


@app.get("/api/v1/pto")
def pto_list(member_id: str = Query("demo")):
    return {"requests": [r.model_dump() for r in pto_svc.list_for(member_id)]}


@app.post("/api/v1/pto/{pto_id}/decide")
def pto_decide(pto_id: str, approve: bool = Query(True)):
    try:
        return pto_svc.decide(pto_id, approve).model_dump()
    except KeyError:
        raise HTTPException(404, f"Unknown PTO request {pto_id}")
