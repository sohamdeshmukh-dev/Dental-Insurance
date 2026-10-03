from datetime import date

from services import tools
from services.benefits import create_reminder


def test_usage_state_and_remaining():
    u = tools.get_benefit_usage(tools.get_plan_details("LFG-123"), tools.get_member("demo"))
    assert u.benefits_remaining == 950
    assert u.percent_used == 36.7
    assert u.state == "plenty_remaining"


def test_reminder_wording_no_loss_framing():
    u = tools.get_benefit_usage(tools.get_plan_details("LFG-123"), tools.get_member("demo"))
    msg = create_reminder(u, date(2026, 11, 1))
    assert msg and "losing" not in msg.lower()
    assert "remaining eligible plan benefits" in msg


def test_no_reminder_outside_window():
    u = tools.get_benefit_usage(tools.get_plan_details("LFG-123"), tools.get_member("demo"))
    assert create_reminder(u, date(2026, 3, 1)) is None
