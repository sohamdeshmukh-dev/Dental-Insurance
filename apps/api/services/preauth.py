"""Out-of-network pre-authorization — SIMULATED Lincoln Financial approval.

In-memory store. The decision is a deterministic mock, clearly labeled demo. No real
submission to any payer and no real approval authority.
"""
from __future__ import annotations

import itertools
from datetime import datetime, timezone

from data.mock import MEMBERS
from schemas import PreAuth, PreAuthCreate
from services import procedures
from services.providers import get_provider

_STORE: dict[str, PreAuth] = {}
_SEQ = itertools.count(1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create(req: PreAuthCreate) -> PreAuth:
    member = MEMBERS[req.member_id]
    provider = get_provider(req.provider_id)
    proc = procedures.CATALOG.get(req.code)
    pa = PreAuth(
        id=f"PA-{next(_SEQ):04d}", member_id=req.member_id, member_name=member.name,
        provider_id=req.provider_id, provider_name=provider.name, code=req.code,
        procedure_name=proc.name if proc else req.code, estimated_cost=req.estimated_cost,
        requested_amount=req.requested_amount, urgency=req.urgency, reason=req.reason,
        status="submitted", submitted_at=_now())
    _STORE[pa.id] = pa
    return pa


def get(item_id: str) -> PreAuth:
    return _STORE[item_id]


def list_for(member_id: str) -> list[PreAuth]:
    return sorted([p for p in _STORE.values() if p.member_id == member_id],
                  key=lambda p: p.submitted_at, reverse=True)


def decide(pa_id: str) -> PreAuth:
    """Mock Lincoln decision: urgent or modest requests auto-approve; large non-urgent get denied."""
    pa = _STORE[pa_id]
    if pa.status != "submitted":
        return pa
    approve = pa.urgency == "urgent" or pa.requested_amount <= 1200
    pa.status = "approved" if approve else "denied"
    pa.decided_at = _now()
    pa.decision_note = ("Approved (demo): urgent care or within out-of-network review threshold."
                        if approve else
                        "Denied (demo): exceeds out-of-network threshold — consider an in-network provider.")
    return pa
