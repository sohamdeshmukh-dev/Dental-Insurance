"""Deterministic loyalty / rewards engine.

Points, tiers, and redemption affordability are CALCULATED here, never by an LLM.

Design principle: rewards are tied to PREVENTIVE and dentist-recommended care, and to staying
in-network. The program never rewards unnecessary, accelerated, or delayed treatment — clinical
urgency always comes first (see CLAUDE.md). Preventive adherence is what dental insurers actually
incentivize, because it reduces later major claims.

PROTOTYPE NOTICE: all prizes, gift cards, sweepstakes, and discounts below are ILLUSTRATIVE demo
values for the CodeLinc prototype. This is not a live financial product and disburses no real money.
"""
from __future__ import annotations

from datetime import date

from schemas import (DentalPlan, Member, RewardEvent, RewardItem, RewardsProfile, RewardTier)

DISCLAIMER = ("Prototype rewards for demonstration only — not a live financial product. "
              "Points, prizes, sweepstakes, and discounts are illustrative. Clinical urgency always "
              "comes first; rewards never depend on getting care you don't need.")

# Points awarded when a preventive / recommended-care claim is paid in-network.
POINT_RULES: dict[str, tuple[str, int]] = {
    "D0120": ("Routine exam completed", 50),
    "D0150": ("Comprehensive exam completed", 60),
    "D0274": ("X-rays completed", 40),
    "D1110": ("Cleaning completed", 100),
    "D1206": ("Fluoride treatment completed", 60),
    "D1351": ("Sealant placed (preventive)", 80),
}
IN_NETWORK_BONUS = 25            # per preventive visit kept in-network
PREVENTIVE_STREAK_BONUS = 200    # both recommended cleanings in the plan year
RECOMMENDED_PLAN_BONUS = 150     # completing a dentist-recommended follow-up (basic/major)

TIERS: list[RewardTier] = [
    RewardTier(name="Bronze", min_points=0, multiplier=1.0,
               perks=["Earn points on every preventive visit"]),
    RewardTier(name="Silver", min_points=500, multiplier=1.1,
               perks=["1.1x points", "Quarterly sweepstakes eligible"]),
    RewardTier(name="Gold", min_points=1500, multiplier=1.25,
               perks=["1.25x points", "2x sweepstakes entries", "Exclusive gift-card catalog"]),
    RewardTier(name="Platinum", min_points=3500, multiplier=1.5,
               perks=["1.5x points", "3x sweepstakes entries", "Priority appointment concierge"]),
]


def _catalog(balance: int) -> list[RewardItem]:
    items = [
        RewardItem(id="gc-amazon-25", name="$25 Amazon gift card", type="gift_card", cost_points=2500,
                   value="$25", detail="Digital gift card delivered by email (demo)."),
        RewardItem(id="gc-target-50", name="$50 Target gift card", type="gift_card", cost_points=4800,
                   value="$50", detail="Digital gift card delivered by email (demo)."),
        RewardItem(id="disc-sealants", name="10% off your next visit", type="discount", cost_points=1500,
                   value="10% off", detail="Applied at your selected in-network dentist's next visit (demo)."),
        RewardItem(id="disc-whitening", name="20% off cosmetic whitening", type="discount", cost_points=2200,
                   value="20% off", detail="At your selected in-network dentist (demo)."),
        RewardItem(id="swp-500", name="Quarterly $500 cash sweepstakes entry", type="cash_sweepstakes",
                   cost_points=500, value="1 entry", detail="Entry into the quarterly $500 cash prize drawing (demo)."),
        RewardItem(id="swp-grand", name="Annual $5,000 grand-prize sweepstakes entry", type="cash_sweepstakes",
                   cost_points=1000, value="1 entry", detail="Entry into the annual grand-prize drawing (demo)."),
        RewardItem(id="swp-spa", name="Wellness spa-day sweepstakes entry", type="sweepstakes",
                   cost_points=400, value="1 entry", detail="Entry into the wellness experience drawing (demo)."),
    ]
    for it in items:
        it.affordable = balance >= it.cost_points
    return items


def _tier_for(points: int) -> RewardTier:
    current = TIERS[0]
    for t in TIERS:
        if points >= t.min_points:
            current = t
    return current


def compute_rewards(plan: DentalPlan, member: Member, lifetime_bonus: int = 0,
                    redeemed_points: int = 0, extra_entries: int = 0) -> RewardsProfile:
    year = plan.plan_year_start.year
    ledger: list[RewardEvent] = []
    cleanings = 0
    for c in sorted(member.claims, key=lambda x: x.service_date):
        if c.service_date.year != year:
            continue
        if c.code in POINT_RULES:
            desc, pts = POINT_RULES[c.code]
            ledger.append(RewardEvent(event_date=c.service_date, code=c.code, description=desc, points=pts))
            if c.network == "in":
                ledger.append(RewardEvent(event_date=c.service_date, code=c.code,
                                          description="In-network visit bonus", points=IN_NETWORK_BONUS))
            if c.code == "D1110":
                cleanings += 1
        elif c.category in ("basic", "major") and c.network == "in":
            ledger.append(RewardEvent(event_date=c.service_date, code=c.code,
                                      description=f"Completed recommended care ({c.description})",
                                      points=RECOMMENDED_PLAN_BONUS))
    if cleanings >= 2:
        last = max(c.service_date for c in member.claims if c.code == "D1110")
        ledger.append(RewardEvent(event_date=last, code="STREAK",
                                  description="Preventive streak: both recommended cleanings this year",
                                  points=PREVENTIVE_STREAK_BONUS))

    earned = sum(e.points for e in ledger)
    lifetime = earned + lifetime_bonus
    tier = _tier_for(lifetime)
    balance = max(0, int(round(earned * tier.multiplier)) + lifetime_bonus - redeemed_points)

    idx = TIERS.index(tier)
    nxt = TIERS[idx + 1] if idx + 1 < len(TIERS) else None
    to_next = max(0, nxt.min_points - lifetime) if nxt else 0
    span = (nxt.min_points - tier.min_points) if nxt else 1
    progress = round(min(100.0, (lifetime - tier.min_points) / span * 100), 1) if nxt else 100.0

    base_entries = 1 if tier.name == "Bronze" else 2 if tier.name in ("Silver", "Gold") else 3
    return RewardsProfile(
        member_id=member.member_id, points_balance=balance, lifetime_points=lifetime,
        tier=tier.name, tier_multiplier=tier.multiplier,
        next_tier=nxt.name if nxt else None, points_to_next_tier=to_next, tier_progress_pct=progress,
        tiers=TIERS, ledger=sorted(ledger, key=lambda e: e.event_date, reverse=True),
        catalog=_catalog(balance), sweepstakes_entries=base_entries + extra_entries,
        earn_rules=[
            "Routine exam — 50 pts", "Cleaning — 100 pts", "X-rays — 40 pts",
            "Fluoride / sealant — 60–80 pts", "In-network visit — +25 pts",
            "Both recommended cleanings in a year — +200 pts",
            "Complete dentist-recommended follow-up care — +150 pts",
        ],
        disclaimer=DISCLAIMER)


def redeem(profile: RewardsProfile, item_id: str) -> tuple[bool, str, int, int]:
    item = next((i for i in profile.catalog if i.id == item_id), None)
    if item is None:
        return False, "That reward isn't available.", profile.points_balance, profile.sweepstakes_entries
    if profile.points_balance < item.cost_points:
        return (False, f"You need {item.cost_points - profile.points_balance} more points for {item.name}.",
                profile.points_balance, profile.sweepstakes_entries)
    new_balance = profile.points_balance - item.cost_points
    entries = profile.sweepstakes_entries + (1 if item.type in ("sweepstakes", "cash_sweepstakes") else 0)
    kind = "confirmed" if item.type in ("sweepstakes", "cash_sweepstakes") else "redeemed"
    return True, f"{item.name} {kind} (demo). {new_balance:,} points remaining.", new_balance, entries
