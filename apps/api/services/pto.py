"""Emergency Paid-Time-Off request + employee work schedule / PTO balance — SIMULATED HR workflow.

Helps an employee request time off for an urgent dental visit. Clearly a demo: no real HR
system is contacted. Urgency-first — this never gates getting care on approval.

All hours arithmetic (balance drawdown, shift overlap, proposed hours) is deterministic and
lives here; the LLM never computes a balance. A submitted request holds hours as `pending`;
approval moves them to `used`, denial releases them back to `available`.
"""
from __future__ import annotations

import itertools
from datetime import date, datetime, timezone

from data.mock import ACCOUNT, MEMBERS, PTO_BALANCES, WORK_SCHEDULES
from schemas import PTOBalance, PTOCreate, PTOProposal, PTORequest, WorkSchedule, WorkScheduleUpdate

DEFAULT_VISIT_HOURS = 4.0

_STORE: dict[str, PTORequest] = {}
_SEQ = itertools.count(1)
# Mutable working copies so a demo drawdown doesn't rewrite the canonical mock fixtures.
_SCHEDULES: dict[str, WorkSchedule] = {k: v.model_copy(deep=True) for k, v in WORK_SCHEDULES.items()}
_BALANCES: dict[str, PTOBalance] = {k: v.model_copy(deep=True) for k, v in PTO_BALANCES.items()}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _recompute(bal: PTOBalance) -> None:
    bal.available_hours = round(bal.accrued_hours - bal.used_hours - bal.pending_hours, 2)


# --- Work schedule -------------------------------------------------------------------------
def get_schedule(member_id: str) -> WorkSchedule:
    if member_id not in _SCHEDULES:
        raise KeyError(f"No work schedule on file for {member_id}")
    return _SCHEDULES[member_id]


def update_schedule(upd: WorkScheduleUpdate) -> WorkSchedule:
    """Apply a partial edit (lets the employee customize their own schedule)."""
    data = get_schedule(upd.member_id).model_dump()
    for field in ("timezone", "work_days", "start_hour", "end_hour", "manager"):
        val = getattr(upd, field)
        if val is not None:
            data[field] = val
    if data["end_hour"] <= data["start_hour"]:
        raise ValueError("end_hour must be after start_hour")
    sched = WorkSchedule(**data)  # re-validates the merged result
    _SCHEDULES[upd.member_id] = sched
    return sched


# --- PTO balance ---------------------------------------------------------------------------
def get_balance(member_id: str) -> PTOBalance:
    if member_id not in _BALANCES:
        raise KeyError(f"No PTO balance on file for {member_id}")
    return _BALANCES[member_id]


# --- Work-hours helpers --------------------------------------------------------------------
def is_work_day(member_id: str, on: date) -> bool:
    sched = _SCHEDULES.get(member_id)
    return bool(sched and on.weekday() in sched.work_days)


def propose_emergency_pto(member_id: str, on: date, reason: str = "Emergency dental visit") -> PTOProposal | None:
    """Draft (never submit) a time-off suggestion when an emergency falls in the member's work hours.

    Returns None when the member has no HR profile or the date is not a working day (no PTO needed).
    """
    sched = _SCHEDULES.get(member_id)
    bal = _BALANCES.get(member_id)
    if sched is None or bal is None or on.weekday() not in sched.work_days:
        return None
    hours = min(DEFAULT_VISIT_HOURS, round(sched.end_hour - sched.start_hour, 2))
    after = round(bal.available_hours - hours, 2)
    msg = ("Your health comes first — please get the care you need. This also falls during your "
           f"work hours, so if it helps I can draft a time-off request to {sched.manager} for about "
           f"{hours:g}h on {on.isoformat()}. It's a draft only; nothing is sent until you confirm.")
    return PTOProposal(
        member_id=member_id, date_needed=on.isoformat(), hours=hours, reason=reason,
        within_work_hours=True, balance_available=bal.available_hours, balance_after=after,
        sufficient_balance=hours <= bal.available_hours, manager=sched.manager, message=msg)


# --- Requests ------------------------------------------------------------------------------
def create(req: PTOCreate) -> PTORequest:
    member = MEMBERS[req.member_id]
    bal = _BALANCES.get(req.member_id)
    if bal is not None:
        if req.hours > bal.available_hours:
            raise ValueError(f"Requested {req.hours:g}h exceeds the available PTO balance of "
                             f"{bal.available_hours:g}h.")
        bal.pending_hours = round(bal.pending_hours + req.hours, 2)
        _recompute(bal)
    r = PTORequest(
        id=f"PTO-{next(_SEQ):04d}", member_id=req.member_id, member_name=member.name,
        employer=ACCOUNT["employer"], date_needed=req.date_needed, hours=req.hours,
        reason=req.reason, status="submitted", submitted_at=_now())
    _STORE[r.id] = r
    return r


def decide(pto_id: str, approve: bool = True) -> PTORequest:
    r = _STORE[pto_id]
    if r.status == "submitted":
        bal = _BALANCES.get(r.member_id)
        if approve:
            r.status = "approved"
            if bal is not None:  # move the held hours from pending into used
                bal.pending_hours = round(bal.pending_hours - r.hours, 2)
                bal.used_hours = round(bal.used_hours + r.hours, 2)
                _recompute(bal)
            r.note = "Approved (demo): emergency medical time off granted — focus on getting care."
        else:
            r.status = "denied"
            if bal is not None:  # release the held hours back to available
                bal.pending_hours = round(bal.pending_hours - r.hours, 2)
                _recompute(bal)
            r.note = "Denied (demo)."
        r.decided_at = _now()
    return r


def get(item_id: str) -> PTORequest:
    return _STORE[item_id]


def list_for(member_id: str) -> list[PTORequest]:
    return sorted([r for r in _STORE.values() if r.member_id == member_id],
                  key=lambda r: r.submitted_at, reverse=True)
