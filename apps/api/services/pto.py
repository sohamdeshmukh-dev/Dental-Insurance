"""Emergency Paid-Time-Off request — SIMULATED HR workflow.

Helps an employee request time off for an urgent dental visit. Clearly a demo: no real HR
system is contacted. Urgency-first — this never gates getting care on approval.
"""
from __future__ import annotations

import itertools
from datetime import datetime, timezone

from data.mock import ACCOUNT, MEMBERS
from schemas import PTOCreate, PTORequest

_STORE: dict[str, PTORequest] = {}
_SEQ = itertools.count(1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create(req: PTOCreate) -> PTORequest:
    member = MEMBERS[req.member_id]
    r = PTORequest(
        id=f"PTO-{next(_SEQ):04d}", member_id=req.member_id, member_name=member.name,
        employer=ACCOUNT["employer"], date_needed=req.date_needed, hours=req.hours,
        reason=req.reason, status="submitted", submitted_at=_now())
    _STORE[r.id] = r
    return r


def decide(pto_id: str, approve: bool = True) -> PTORequest:
    r = _STORE[pto_id]
    if r.status == "submitted":
        r.status = "approved" if approve else "denied"
        r.decided_at = _now()
        r.note = ("Approved (demo): emergency medical time off granted — focus on getting care."
                  if approve else "Denied (demo).")
    return r


def get(item_id: str) -> PTORequest:
    return _STORE[item_id]


def list_for(member_id: str) -> list[PTORequest]:
    return sorted([r for r in _STORE.values() if r.member_id == member_id],
                  key=lambda r: r.submitted_at, reverse=True)
