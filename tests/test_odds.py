"""Odds enhancers: the four questions, their points, and what the total means."""

import pytest

from desk import Zone, ZoneQuality, entry_action, exit_action, plan_zone_trade, score_zone
from desk.odds import (
    CONFIRMATION_ENTRY, EXIT_BEFORE_ZONE, LIMIT_ENTRY, RIDE_THROUGH, SKIP_ZONE, WATCH_FOR_TURN,
)


@pytest.mark.parametrize("ratio,points", [(6.1, 2), (3.0, 2), (2.99, 1), (2.0, 1), (1.99, 0), (0.5, 0)])
def test_reward_risk_points(ratio, points):
    assert score_zone(ratio, ZoneQuality("long", 1, 0)).reward_risk == points


@pytest.mark.parametrize("leg,points", [("long", 2), ("medium", 1), ("small", 0), ("Long", 2)])
def test_leg_out_points(leg, points):
    assert score_zone(3, ZoneQuality(leg, 1, 0)).leg_out == points


@pytest.mark.parametrize("candles,points", [(1, 2), (2, 2), (3, 1), (4, 1), (5, 0), (9, 0)])
def test_time_in_zone_points(candles, points):
    assert score_zone(3, ZoneQuality("long", candles, 0)).time_in_zone == points


@pytest.mark.parametrize("revisits,points", [(0, 2), (1, 1), (2, 0), (5, 0)])
def test_freshness_points(revisits, points):
    assert score_zone(3, ZoneQuality("long", 1, revisits)).freshness == points


@pytest.mark.parametrize(
    "total,entry,exit_",
    [
        (8, LIMIT_ENTRY, EXIT_BEFORE_ZONE),
        (7, LIMIT_ENTRY, EXIT_BEFORE_ZONE),
        (6, CONFIRMATION_ENTRY, WATCH_FOR_TURN),
        (5, CONFIRMATION_ENTRY, WATCH_FOR_TURN),
        (4, SKIP_ZONE, RIDE_THROUGH),
        (0, SKIP_ZONE, RIDE_THROUGH),
    ],
)
def test_what_the_total_means(total, entry, exit_):
    assert entry_action(total) == entry
    assert exit_action(total) == exit_


def test_perfect_zone_is_a_limit_entry():
    plan = plan_zone_trade(
        "HD", "long", Zone(141.98, 141.29), Zone(149.94, 148.93), 2.21, 250,
        entry_zone_quality=ZoneQuality("long", 2, 0),
    )
    assert plan.odds.total == 8
    assert plan.entry_type == LIMIT_ENTRY
    assert plan.approved


def test_middling_zone_is_a_confirmation_entry():
    plan = plan_zone_trade(
        "HD", "long", Zone(141.98, 141.29), Zone(149.94, 148.93), 2.21, 250,
        entry_zone_quality=ZoneQuality("medium", 3, 1),  # 2 + 1 + 1 + 1
    )
    assert plan.odds.total == 5
    assert plan.entry_type == CONFIRMATION_ENTRY
    assert plan.approved


def test_weak_zone_is_skipped_even_with_good_reward_to_risk():
    plan = plan_zone_trade(
        "HD", "long", Zone(141.98, 141.29), Zone(149.94, 148.93), 2.21, 250,
        entry_zone_quality=ZoneQuality("small", 5, 1),  # 2 + 0 + 0 + 1
    )
    assert plan.odds.total == 3
    assert plan.entry_type == SKIP_ZONE
    assert not plan.approved


def test_ungraded_zone_has_no_odds_check():
    plan = plan_zone_trade("HD", "long", Zone(141.98, 141.29), Zone(149.94, 148.93), 2.21, 250)
    assert plan.odds is None and plan.entry_type is None


@pytest.mark.parametrize("days,ok", [(10, True), (4, True), (3, False), (0, False), (-2, False), (-4, True)])
def test_earnings_window(days, ok):
    plan = plan_zone_trade(
        "HD", "long", Zone(141.98, 141.29), Zone(149.94, 148.93), 2.21, 250,
        days_to_earnings=days,
    )
    assert plan.approved is ok


@pytest.mark.parametrize("args", [("huge", 1, 0), ("long", 0, 0), ("long", 1, -1)])
def test_bad_zone_readings_raise(args):
    with pytest.raises(ValueError):
        ZoneQuality(*args)
