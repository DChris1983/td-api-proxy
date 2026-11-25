"""Zone finder, guide and daily report, on a hand-built chart."""

import pytest

from desk.guide import GuideSettings, build_daily_report, build_guide
from desk.market import atr, rsi, sma
from desk.odds import LIMIT_ENTRY
from desk.zones import find_zones, nearest_buyer_zone, nearest_seller_zone
from tests import sample_market as sample


def test_indicators_on_simple_series():
    assert sma([1, 2, 3, 4], 2) == 3.5
    assert sma([1, 2], 5) is None
    assert rsi(list(range(1, 40))) == 100.0
    assert rsi([10, 9] * 20) == pytest.approx(50, abs=5)
    assert 0.9 < atr(sample.between_levels()[:60]) < 1.1  # quiet days: range about a dollar


def test_finds_the_two_standing_zones():
    candles = sample.between_levels()
    zones = find_zones(candles)
    price = candles[-1].close

    buyer = nearest_buyer_zone(zones, price)
    assert (buyer.proximal, buyer.distal) == (95.5, 94.9)  # top of base bodies, lowest wick
    assert (buyer.base_candles, buyer.leg_out, buyer.revisits) == (2, "long", 0)

    seller = nearest_seller_zone(zones, price)
    assert (seller.proximal, seller.distal) == (110.0, 110.6)  # bottom of base bodies, highest wick
    assert (seller.base_candles, seller.leg_out, seller.revisits) == (2, "long", 0)


def test_broken_zone_is_dropped():
    # The rally left a buyer zone at 100; the later drop closed through it.
    zones = find_zones(sample.between_levels())
    assert not [z for z in zones if z.side == "buyer" and 99 < z.proximal < 101]


def test_between_levels_means_wait_and_set_an_alert():
    g = build_guide("xyz", sample.between_levels())
    zone = g["zone_method"]
    assert g["ticker"] == "XYZ" and g["price"] == 99.5
    assert zone["status"] == "between_levels" and not zone["standout"]
    assert zone["plan"]["entry"] == 95.5 and zone["plan"]["target"] == 110.0
    assert zone["plan"]["odds_score"] == 8 and zone["plan"]["passes"]
    assert "Set an alert at 95.50" in zone["action"]


def test_at_the_buyer_zone_gives_the_orders():
    g = build_guide("XYZ", sample.back_at_the_zone(), settings=GuideSettings(loss_threshold=250))
    zone, plan = g["zone_method"], g["zone_method"]["plan"]
    assert zone["status"] == "at_buyer_zone" and zone["standout"] and g["standout"]
    assert plan["entry"] == 95.5 and plan["entry_type"] == LIMIT_ENTRY
    assert plan["stop"] < 94.9  # below the far line by 20% of the average daily move
    assert plan["reward_risk"] >= 3 and plan["max_loss"] <= 250
    assert "Buy limit 95.50" in zone["action"]


def test_earnings_window_blocks_the_trade():
    g = build_guide("XYZ", sample.back_at_the_zone(), days_to_earnings=2)
    assert g["zone_method"]["status"] == "at_buyer_zone_fails"
    assert not g["standout"]


def test_no_seller_zone_at_all_time_highs():
    g = build_guide("XYZ", sample.all_time_high())
    assert g["zone_method"]["status"] == "no_seller_zone"
    assert "all-time highs" in g["zone_method"]["action"]


def test_too_little_history():
    assert "error" in build_guide("XYZ", sample.between_levels()[:30])


def _with_calls(**settings):
    candles = sample.between_levels()
    today, price = candles[-1].day, candles[-1].close
    return build_guide("XYZ", candles, sample.call_chain(today, price),
                       settings=GuideSettings(**settings)), price


def test_long_calls_flags_the_contract_that_is_down_enough():
    g, price = _with_calls(option_budget=2000)
    call = g["long_call_method"]
    assert all(c["passed"] for c in call["stock_checks"])
    assert call["standout"] and g["standout"]

    rows = call["far_dated"]
    assert len({r["expiration"] for r in rows}) == 1  # only the furthest expiration is offered
    assert rows[0]["expiration"] == call["furthest_expiration"]
    best = rows[0]
    assert best["favorable"] and best["strike"] == round(price * 1.25)
    assert best["drop_from_high_pct"] == 45 and best["limit_price"] == 5.5
    assert best["cost_per_contract"] == 550 and best["contracts_within_budget"] == 3
    assert "like_class_example" in best
    assert [r["favorable"] for r in rows].count(True) == 1
    assert any("no price history" in r["verdict"] for r in rows)
    assert "never above the ask of 5.60" in call["action"]


def test_swing_example_picks_the_strike_eight_to_nine_percent_out():
    g, price = _with_calls()
    swing = g["long_call_method"]["swing_example"]
    assert swing["strike"] == round(price * 1.085) and 40 <= swing["days_left"] <= 46


def test_budget_too_small_means_no_favorable_call():
    g, _ = _with_calls(option_budget=300)
    assert not g["long_call_method"]["standout"]


def test_thin_stock_gets_no_calls():
    candles = [c.__class__(c.day, c.open, c.high, c.low, c.close, 100_000) for c in sample.between_levels()]
    g = build_guide("XYZ", candles, sample.call_chain(candles[-1].day, candles[-1].close))
    assert not g["long_call_method"]["standout"]
    assert "fails the checks" in g["long_call_method"]["action"]


def test_daily_report_sorts_the_watchlist():
    charts = {"ATZONE": sample.back_at_the_zone(), "WAIT": sample.between_levels(), "HIGH": sample.all_time_high()}

    def fetch(ticker):
        if ticker == "BROKEN":
            raise RuntimeError("no data")
        candles = charts[ticker]
        calls = sample.call_chain(candles[-1].day, candles[-1].close) if ticker == "WAIT" else None
        return build_guide(ticker, candles, calls, GuideSettings(option_budget=2000))

    report = build_daily_report(["ATZONE", "WAIT", "HIGH", "BROKEN"], fetch)
    assert [s["ticker"] for s in report["stocks_at_a_buyer_zone"]] == ["ATZONE"]
    assert [s["ticker"] for s in report["calls_priced_favorably"]] == ["WAIT"]
    assert [a["ticker"] for a in report["alerts_to_set"]] == ["WAIT"]
    assert report["alerts_to_set"][0]["alert_at"] == 95.5
    assert report["nothing_today"] == ["HIGH"]
    assert report["errors"] == [{"ticker": "BROKEN", "error": "no data"}]
