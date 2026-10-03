from datetime import date

from services import tools
from services.providers import active_membership

PLAN = tools.get_plan_details("LFG-123")


def test_out_of_network_provider_excluded_by_default():
    res = tools.search_network_providers(PLAN, "19122", date(2026, 10, 1), radius=20)
    ids = {r.provider.provider_id for r in res}
    assert "P005" not in ids  # no membership record
    assert all(r.network_status == "VERIFIED_IN_NETWORK" for r in res)


def test_terminated_membership_not_in_network():
    # P006 contract terminated 2026-06-30
    assert active_membership("P006", "LINCOLN_PPO", date(2026, 10, 1)) is None
    assert active_membership("P006", "LINCOLN_PPO", date(2026, 3, 1)) is not None


def test_results_sorted_by_distance():
    res = tools.search_network_providers(PLAN, "19122", date(2026, 10, 1), radius=20, include_out_of_network=True)
    assert [r.distance_miles for r in res] == sorted(r.distance_miles for r in res)
