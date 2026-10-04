from datetime import date

from data.mock import MEMBERS, PLAN
from services import tools
from services.coverage import calculate_coverage, money
from services.procedures import CATALOG


def member():
    return MEMBERS["demo"].model_copy(deep=True)


def test_major_in_network_crown_math():
    # allowed 1100*1.0, deductible 50, 50% coinsurance, within remaining max (1500-550=950)
    r = tools.calculate_coverage(PLAN, member(), "D2740", "in", date(2026, 10, 1))
    assert r.allowed_amount == 1100
    assert r.deductible_applied == 50
    assert r.coinsurance_pct == 0.5
    assert r.plan_payment_before_max == 525  # (1100-50)*0.5
    assert r.plan_payment == 525
    assert r.member_payment == 575  # 1100 - 525
    assert not r.annual_max_applied


def test_annual_maximum_caps_payment():
    m = member()
    m.benefits_used = 1700  # only 300 remaining of the $2,000 max
    r = tools.calculate_coverage(PLAN, m, "D2740", "in", date(2026, 10, 1))
    assert r.plan_payment_before_max == 525
    assert r.plan_payment == 300
    assert r.annual_max_applied
    assert r.member_payment == 800  # 1100 - 300


def test_preventive_exempt_from_deductible_full_coverage():
    m = member()
    m.history = []  # avoid frequency limit
    r = tools.calculate_coverage(PLAN, m, "D0120", "in", date(2026, 10, 1))
    assert r.deductible_applied == 0
    assert r.coinsurance_pct == 1.0
    assert r.member_payment == 0


def test_out_of_network_balance_billing():
    r_in = tools.calculate_coverage(PLAN, member(), "D3330", "in", date(2026, 10, 1))
    r_out = tools.calculate_coverage(PLAN, member(), "D3330", "out", date(2026, 10, 1))
    # out-of-network member pays more: lower coinsurance + balance over allowed
    assert r_out.member_payment > r_in.member_payment
    assert r_out.provider_charge > r_out.allowed_amount


def test_frequency_limit_denies_second_cleaning():
    m = member()
    m.history = [__import__("schemas").ServiceRecord(code="D1110", service_date=date(2026, 3, 1)),
                 __import__("schemas").ServiceRecord(code="D1110", service_date=date(2026, 6, 1))]
    r = tools.calculate_coverage(PLAN, m, "D1110", "in", date(2026, 9, 1))
    assert not r.covered
    assert "Frequency" in r.denial_reason


def test_waiting_period_denial():
    m = member()
    m.coverage_effective_date = date(2026, 8, 1)  # < 6 months before major service
    r = tools.calculate_coverage(PLAN, m, "D2740", "in", date(2026, 10, 1))
    assert not r.covered
    assert "waiting period" in r.denial_reason


def test_money_rounding():
    assert money("10.005") == money("10.01")


def test_remaining_after_and_savings_come_from_engine():
    from services import tools
    from services.coverage import in_network_savings
    plan, member = tools.get_plan_details("LFG-123"), tools.get_member("demo")
    in_net = tools.calculate_coverage(plan, member, "D3330", "in", date(2026, 10, 1))
    out_net = tools.calculate_coverage(plan, member, "D3330", "out", date(2026, 10, 1))
    usage = tools.get_benefit_usage(plan, member)
    assert in_net.annual_max_remaining_after == usage.benefits_remaining - in_net.plan_payment
    assert out_net.annual_max_remaining_after == usage.benefits_remaining - out_net.plan_payment
    assert in_network_savings(in_net, out_net) == out_net.member_payment - in_net.member_payment
