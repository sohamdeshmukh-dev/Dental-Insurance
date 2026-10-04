from schemas import PTOCreate
from services import pto


def test_pto_create_and_approve():
    r = pto.create(PTOCreate(member_id="demo", date_needed="2026-10-05", hours=4, reason="Emergency dental visit"))
    assert r.status == "submitted" and r.employer == "Acme Co" and r.member_name == "Jordan Lee"
    out = pto.decide(r.id, True)
    assert out.status == "approved" and "emergency" in out.note.lower()
    assert any(x.id == r.id for x in pto.list_for("demo"))
