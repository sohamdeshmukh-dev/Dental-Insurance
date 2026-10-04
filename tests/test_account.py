from services import tools

PLAN = tools.get_plan_details("LFG-123")


def test_annual_maximum_is_2000():
    assert PLAN.annual_maximum == 2000


def test_account_has_guardian_and_dependent():
    acct = tools.get_account()
    assert acct.guardian_id == "demo"
    rels = {m.member_id: m.relationship for m in acct.members}
    assert rels == {"demo": "guardian", "demo-child": "dependent"}
    child = next(m for m in acct.members if m.member_id == "demo-child")
    assert child.name == "Riley Lee" and child.age == 9


def test_each_member_has_own_2000_limit_and_usage():
    acct = tools.get_account()
    for m in acct.members:
        assert m.annual_maximum == 2000
    guardian = next(m for m in acct.members if m.relationship == "guardian")
    child = next(m for m in acct.members if m.relationship == "dependent")
    assert guardian.benefits_used == 550 and guardian.benefits_remaining == 1450
    assert child.benefits_used == 220  # 50+40+85+45 pediatric preventive
    assert child.benefits_remaining == 1780
    assert guardian.benefits_used != child.benefits_used  # isolated


def test_child_earns_preventive_rewards_from_own_claims():
    child = tools.get_member("demo-child")
    r = tools.get_rewards(PLAN, child)
    assert r.lifetime_points > 0           # kid earns points for preventive care
    assert r.lifetime_points < 1180        # but starts fresh (no guardian prior-year bonus)
