"""Tests for the employee time-off feature: work schedule, PTO balance, drawdown, and the
in-work-hours emergency proposal. Balance assertions use deltas so they're order-independent
(the in-memory store persists across tests in one process)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from schemas import PTOCreate, WorkScheduleUpdate
from services import pto

client = TestClient(app)

MONDAY = date(2026, 10, 5)      # a working day
SATURDAY = date(2026, 10, 3)    # not a working day


def test_schedule_and_balance_endpoints():
    sched = client.get("/api/v1/employee/schedule?member_id=demo").json()
    assert sched["work_days"] == [0, 1, 2, 3, 4] and sched["manager"] == "Dana Brooks" and sched["demo"]
    bal = client.get("/api/v1/pto/balance?member_id=demo").json()
    assert bal["available_hours"] == round(bal["accrued_hours"] - bal["used_hours"] - bal["pending_hours"], 2)


def test_no_profile_for_dependent_is_404():
    assert client.get("/api/v1/employee/schedule?member_id=demo-child").status_code == 404
    assert client.get("/api/v1/pto/balance?member_id=demo-child").status_code == 404
    assert client.get("/api/v1/employee/schedule?member_id=nobody").status_code == 404


def test_schedule_edit_is_applied_and_validated():
    out = client.put("/api/v1/employee/schedule",
                     json={"member_id": "demo", "start_hour": 8, "end_hour": 16, "manager": "Sam Rivera"}).json()
    assert out["start_hour"] == 8 and out["end_hour"] == 16 and out["manager"] == "Sam Rivera"
    # restore so later tests see the default window
    client.put("/api/v1/employee/schedule", json={"member_id": "demo", "start_hour": 9, "end_hour": 17, "manager": "Dana Brooks"})
    # a window with end <= start is rejected
    assert client.put("/api/v1/employee/schedule", json={"member_id": "demo", "start_hour": 18}).status_code == 400
    with pytest.raises(ValidationError):
        WorkScheduleUpdate(work_days=[0, 7])


def test_balance_drawn_down_on_approval_and_released_on_denial():
    before = pto.get_balance("demo").available_hours
    r = pto.create(PTOCreate(member_id="demo", date_needed="2026-10-05", hours=6))
    assert pto.get_balance("demo").available_hours == round(before - 6, 2)  # held as pending
    pto.decide(r.id, True)
    assert pto.get_balance("demo").available_hours == round(before - 6, 2)  # pending -> used, still out
    assert pto.get_balance("demo").used_hours >= 6

    before2 = pto.get_balance("demo").available_hours
    r2 = pto.create(PTOCreate(member_id="demo", date_needed="2026-10-06", hours=5))
    pto.decide(r2.id, False)
    assert pto.get_balance("demo").available_hours == round(before2, 2)  # released back


def test_request_exceeding_balance_is_rejected():
    # Draw the balance down below the per-request field cap (80h) so "exceeds balance" is
    # reachable, but leave enough for other tests that request a few hours.
    while pto.get_balance("demo").available_hours > 30:
        held = pto.create(PTOCreate(member_id="demo", date_needed="2026-10-07",
                                    hours=min(40, pto.get_balance("demo").available_hours)))
        pto.decide(held.id, True)
    avail = pto.get_balance("demo").available_hours
    r = client.post("/api/v1/pto", json={"member_id": "demo", "date_needed": "2026-10-07", "hours": avail + 10})
    assert r.status_code == 400 and "exceeds" in r.json()["detail"]


def test_proposal_only_within_work_hours():
    workday = pto.propose_emergency_pto("demo", MONDAY)
    assert workday is not None and workday.within_work_hours and workday.hours == 4
    assert workday.balance_after == round(workday.balance_available - workday.hours, 2)
    assert pto.propose_emergency_pto("demo", SATURDAY) is None       # weekend -> no PTO needed
    assert pto.propose_emergency_pto("demo-child", MONDAY) is None   # no HR profile


def test_emergency_agent_message_attaches_proposal_in_hours():
    r = client.post("/api/v1/agent/message",
                    json={"member_id": "demo", "message": "my face is swollen and I have a high fever",
                          "today": "2026-10-05"}).json()
    assert r["status"] == "EMERGENCY"
    assert r["pto_proposal"]["within_work_hours"] and r["pto_proposal"]["manager"] == "Dana Brooks"
    # weekend emergency: still an emergency, but no PTO proposal
    r2 = client.post("/api/v1/agent/message",
                     json={"member_id": "demo", "message": "my face is swollen and I have a high fever",
                           "today": "2026-10-03"}).json()
    assert r2["status"] == "EMERGENCY" and "pto_proposal" not in r2
