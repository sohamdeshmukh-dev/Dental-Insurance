from datetime import date

from services import tools

PLAN = tools.get_plan_details("LFG-123")


def member():
    return tools.get_member("demo").model_copy(deep=True)


def test_root_canal_sequenced_before_crown():
    cp = tools.optimize_treatment_sequence(PLAN, member(), ["D2740", "D3330"], set(), "in", date(2026, 10, 1))
    codes = [i.code for i in cp.items]
    assert codes.index("D3330") < codes.index("D2740")


def test_urgent_overrides_financial_optimization():
    m = member()
    m.benefits_used = 1400  # almost exhausted
    cp = tools.optimize_treatment_sequence(PLAN, m, ["D3330"], {"D3330"}, "in", date(2026, 11, 1))
    assert cp.items[0].plan_year == 2026
    assert "URGENT_SCHEDULE_EARLIEST" in cp.items[0].reason_codes


def test_non_urgent_may_defer_to_next_year():
    m = member()
    m.benefits_used = 1450  # 50 remaining -> next year cheaper
    cp = tools.optimize_treatment_sequence(PLAN, m, ["D2740"], set(), "in", date(2026, 11, 1))
    assert cp.items[0].plan_year == 2027
