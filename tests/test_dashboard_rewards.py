from datetime import date

from services import tools
from services.rewards import compute_rewards, redeem

PLAN = tools.get_plan_details("LFG-123")


def member():
    return tools.get_member("demo").model_copy(deep=True)


def test_funding_timeline_cumulative_matches_benefits_used():
    tl = tools.get_funding_timeline(PLAN, member(), date(2026, 10, 1))
    assert tl.months[-1].cumulative_used == tl.benefits_used == 550
    # cumulative is monotonically non-decreasing
    cums = [m.cumulative_used for m in tl.months]
    assert cums == sorted(cums)
    # remaining never goes negative, ends at annual_max - used
    assert tl.months[-1].remaining == 1500 - 550
    assert tl.benefits_remaining == 950


def test_funding_by_category_sums_to_used():
    tl = tools.get_funding_timeline(PLAN, member(), date(2026, 10, 1))
    assert round(sum(tl.by_category.values()), 2) == 550
    assert tl.by_category["preventive"] == 310  # 55+70+90+95
    assert tl.by_category["basic"] == 240        # 120+120


def test_rewards_points_from_preventive_care():
    # pure earned points (no lifetime bonus) are deterministic from claims:
    #   exam 50 + xray 40 + clean 100 + clean 100         (preventive base)
    # + in-network bonus 25 x4 preventive visits          = 100
    # + recommended-care bonus 150 x2 in-network fillings  = 300
    # + preventive streak (two cleanings)                  = 200
    #   -> 290 + 100 + 300 + 200 = 890
    p = compute_rewards(PLAN, member(), lifetime_bonus=0)
    assert p.lifetime_points == 890
    assert any(e.code == "STREAK" for e in p.ledger)
    assert p.disclaimer.lower().startswith("prototype")


def test_tier_and_progress():
    p = compute_rewards(PLAN, member(), lifetime_bonus=1180)  # 890+1180=2070 -> Gold (>=1500)
    assert p.tier == "Gold"
    assert p.next_tier == "Platinum"
    assert 0 < p.tier_progress_pct <= 100
    assert p.points_to_next_tier == 3500 - 2070


def test_catalog_affordability_flags():
    p = compute_rewards(PLAN, member(), lifetime_bonus=1180)
    swp = next(i for i in p.catalog if i.id == "swp-500")
    assert swp.affordable  # 500 pts, balance well above
    assert all(i.demo for i in p.catalog)


def test_redeem_insufficient_points():
    p = compute_rewards(PLAN, member(), lifetime_bonus=0, redeemed_points=10_000)  # force low balance
    ok, msg, bal, entries = redeem(p, "gc-target-50")
    assert not ok and "more points" in msg


def test_redeem_sweepstakes_adds_entry():
    p = compute_rewards(PLAN, member(), lifetime_bonus=1180)
    before = p.sweepstakes_entries
    ok, msg, bal, entries = redeem(p, "swp-500")
    assert ok and entries == before + 1 and bal == p.points_balance - 500
