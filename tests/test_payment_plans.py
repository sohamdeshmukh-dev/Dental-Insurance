from datetime import date

from schemas import PaymentPlanCreate
from services import payment_plans as pp


def test_create_computes_total_and_schedule():
    p = pp.create(PaymentPlanCreate(member_id="demo", provider_id="P001", codes=["D2740"], term_months=10), on=date(2026, 10, 1))
    assert p.status == "draft" and p.total > 0
    assert len(p.schedule) == 10
    assert round(sum(r.amount for r in p.schedule), 2) == p.total  # rounding absorbed
    assert p.monthly_amount == round(p.total / 10, 2)


def test_state_machine_approve():
    p = pp.create(PaymentPlanCreate(member_id="demo", provider_id="P001", codes=["D2740"], term_months=6), on=date(2026, 10, 1))
    assert pp.send_to_doctor(p.id).status == "sent_to_doctor"
    out = pp.doctor_decision(p.id, True)
    assert out.status == "active" and "active" in out.audit[-1].event.lower()


def test_state_machine_decline_and_list():
    p = pp.create(PaymentPlanCreate(member_id="demo", provider_id="P001", codes=["D1110"], term_months=3), on=date(2026, 10, 1))
    pp.send_to_doctor(p.id)
    assert pp.doctor_decision(p.id, False).status == "declined"
    assert any(x.id == p.id for x in pp.list_for("demo"))


def test_cannot_approve_before_send():
    p = pp.create(PaymentPlanCreate(member_id="demo", provider_id="P001", codes=["D2740"], term_months=12), on=date(2026, 10, 1))
    assert pp.doctor_decision(p.id, True).status == "draft"  # ignored until sent
