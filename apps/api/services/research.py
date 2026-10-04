"""Background research briefs: after the member asks about a procedure, the Bedrock agent
keeps working without them and leaves a brief to pick up on their next visit.

Same contract as the live agent: the model only chooses tools and narrates; every number comes
from the deterministic services via ``bedrock_agent.run``.

Flow (works on serverless, where nothing may run after a response is sent): ``queue`` records a
PENDING brief during the chat request; the page then calls ``POST /research/{id}/run``, which
does the work inside its own request via ``run_pending``.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Callable, Optional

from services import bedrock_agent, brief_store, tools

DISCLAIMER = "Estimates only — actual benefits are determined when the claim is processed."

PROMPT = (
    "The member is no longer online. Earlier they wrote: {message!r}. That was matched to CDT "
    "code(s) {codes}. Write a short research brief they will read on their next visit, addressed "
    "to them directly as 'you' (never 'the member'), using tools for every "
    "fact: (1) in-network vs out-of-network cost for each code, (2) their remaining annual maximum "
    "and deductible, and whether this treatment fits within it, (3) a recommended timing/sequence, "
    "(4) nearby verified in-network offices, only if their message included a ZIP code; otherwise "
    "say a ZIP code is needed. Quote dollar amounts exactly as tools return them; never add, "
    "subtract or otherwise derive a new figure yourself; for the annual maximum left after a "
    "procedure use annual_max_remaining_after, and for the in- vs out-of-network difference use "
    "in_network_savings. Mark a code as urgent only if the "
    "member's message described pain, swelling, infection or an emergency, and if so say it "
    "before any cost advice. Do not ask questions; state what is missing instead. Write short "
    "plain paragraphs with **bold** labels only: no headings, tables, bullet lists or emoji."
)


def codes_from(result: dict) -> list[str]:
    """CDT codes an agent response actually priced, from either engine's response shape."""
    codes = [p["selected_code"] for p in result.get("procedures", [])]
    codes += [c["input"].get("code") for c in result.get("tool_calls", [])
              if c["tool"] == "compare_networks" and c["status"] == "success"]
    return sorted({c for c in codes if c})


def queue(session_id: Optional[str], result: dict, message: str, today: Optional[date]) -> bool:
    """Record a PENDING brief if this response identified a procedure that isn't already being
    researched. True means the page should now call the run endpoint."""
    codes = codes_from(result)
    if not session_id or not codes or not bedrock_agent.bedrock_enabled():
        return False
    existing = brief_store.get(session_id) or {}
    # RUNNING or READY for the same codes: don't pay for the same brief twice. PENDING (its run
    # request never arrived) and FAILED get another go; claim() makes a double run impossible.
    if existing.get("codes") == codes and existing.get("status") in ("RUNNING", "READY"):
        return False
    brief_store.put(session_id, {"status": "PENDING", "codes": codes, "message": message,
                                 "today": today.isoformat() if today else None})
    return True


def run_pending(session_id: str, converse: Optional[Callable[..., dict]] = None) -> dict:
    """Run the queued brief if this caller wins the claim; otherwise report what's there."""
    if not brief_store.claim(session_id):
        return brief_store.get(session_id) or {"status": "NONE"}
    job = brief_store.get(session_id)
    return run_research(session_id, job["codes"], job["message"],
                        date.fromisoformat(job["today"]) if job.get("today") else None, converse)


def run_research(session_id: str, codes: list[str], message: str, today: Optional[date] = None,
                 converse: Optional[Callable[..., dict]] = None) -> dict:
    try:
        out = bedrock_agent.run(PROMPT.format(message=message, codes=", ".join(codes)),
                                today=today, session_id=session_id, converse=converse)
        brief = {"status": "READY", "codes": codes, "brief": out["explanation"],
                 "procedures": [tools.lookup_procedure(c).name for c in codes],
                 "tool_calls": out["tool_calls"], "trace": out["trace"], "disclaimer": DISCLAIMER}
    except Exception as exc:  # a background job has no caller to raise to; record the failure
        brief = {"status": "FAILED", "codes": codes, "error": str(exc)}
    brief["created_at"] = datetime.now(timezone.utc).isoformat()
    brief_store.put(session_id, brief)
    return brief
