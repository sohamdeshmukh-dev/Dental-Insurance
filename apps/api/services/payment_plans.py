"""Payment-plan workflow — SIMULATED agreement (no real money, no e-signature).

The amount financed is the member's estimated responsibility for the chosen procedures at the
chosen clinic (from the deterministic coverage engine). The monthly amount and amortization
schedule are computed here, deterministically. A plan moves draft -> sent_to_doctor ->
active/declined via mock doctor approval. Clearly a demo; nothing executes a real contract.
"""
from __future__ import annotations

import itertools
from datetime import date, datetime, timezone

from data.mock import MEMBERS
from schemas import (AuditEntry, PaymentItem, PaymentPlan, PaymentPlanCreate, ScheduleEntry)
from services import clinic, procedures
from services.providers import get_provider

_STORE: dict[str, PaymentPlan] = {}
_SEQ = itertools.count(1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, min(d.day, 28))


def _schedule(total: float, term: int, start: date) -> tuple[float, list[ScheduleEntry]]:
    monthly = round(total / term, 2)
    rows, running = [], 0.0
    for i in range(term):
        amt = round(total - running, 2) if i == term - 1 else monthly  # last row absorbs rounding
        running = round(running + amt, 2)
        rows.append(ScheduleEntry(n=i + 1, due_date=_add_months(start, i + 1).isoformat(), amount=amt))
    return monthly, rows


def create(req: PaymentPlanCreate, on: date | None = None) -> PaymentPlan:
    on = on or date.today()
    member = MEMBERS[req.member_id]
    provider = get_provider(req.provider_id)
    est = {s.code: s for s in clinic.clinic_estimates(member, req.provider_id, on).services}
    items: list[PaymentItem] = []
    for code in req.codes:
        proc = procedures.CATALOG.get(code)
        cost = est[code].member_pays if code in est else 0.0
        items.append(PaymentItem(code=code, name=proc.name if proc else code, cost=round(cost, 2)))
    total = round(sum(i.cost for i in items), 2)
    term = max(1, min(req.term_months, 60))
    monthly, sched = _schedule(total, term, on)
    pp = PaymentPlan(
        id=f"PP-{next(_SEQ):04d}", member_id=req.member_id, member_name=member.name,
        provider_id=provider.provider_id, provider_name=provider.name, items=items, total=total,
        term_months=term, monthly_amount=monthly, status="draft", schedule=sched,
        audit=[AuditEntry(at=_now(), event="Plan drafted")], created_at=_now())
    _STORE[pp.id] = pp
    return pp


def send_to_doctor(pp_id: str) -> PaymentPlan:
    pp = _STORE[pp_id]
    if pp.status == "draft":
        pp.status = "sent_to_doctor"
        pp.audit.append(AuditEntry(at=_now(), event=f"Sent to {pp.provider_name} for approval"))
    return pp


def doctor_decision(pp_id: str, approve: bool) -> PaymentPlan:
    pp = _STORE[pp_id]
    if pp.status == "sent_to_doctor":
        if approve:
            pp.status = "active"
            pp.audit.append(AuditEntry(at=_now(), event="Approved by dentist — agreement active (simulated)"))
        else:
            pp.status = "declined"
            pp.audit.append(AuditEntry(at=_now(), event="Declined by dentist"))
    return pp


def list_for(member_id: str) -> list[PaymentPlan]:
    return sorted([p for p in _STORE.values() if p.member_id == member_id],
                  key=lambda p: p.created_at, reverse=True)
