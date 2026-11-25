"""Long-dated call checklist."""

from datetime import date

import pytest

from desk import LongCallRules, screen_long_call

TODAY = date(2026, 11, 25)


def screen(**overrides):
    """A contract that passes everything; tests change one thing at a time."""
    args = dict(
        ticker="meta", strike=600, expiration=date(2028, 12, 15),
        contract_high=120.0, bid=68.0, ask=71.0, limit_price=70.0,
        underlying_volume=15_000_000, rsi=55,
        money_prepared_to_lose=8000, checked_why_it_dropped=True,
        today=TODAY,
    )
    args.update(overrides)
    return screen_long_call(**args)


def failed(plan):
    return [c.name for c in plan.failures]


def test_good_contract_passes():
    plan = screen()
    assert plan.approved
    assert plan.ticker == "META"
    assert plan.days_to_expiration == 751
    assert plan.contract_drop == pytest.approx(0.4167, abs=1e-4)  # 120 down to 70
    assert plan.cost == 7000.00  # 70 x 100 shares x 1 contract
    assert plan.trailing_stops == [63.00, 56.00]  # 10% and 20% under the price paid


def test_contract_must_be_down_forty_percent():
    plan = screen(limit_price=75.0, bid=74.0, ask=76.0)  # down 37.5%
    assert failed(plan) == ["contract is down at least 40%"]


def test_exactly_forty_percent_passes():
    assert screen(limit_price=72.0, bid=71.0, ask=73.0).approved  # 120 -> 72


def test_sideways_or_rising_contract_is_rejected():
    plan = screen(contract_high=33.0, limit_price=34.0, bid=33.5, ask=34.5, money_prepared_to_lose=5000)
    assert "contract is down at least 40%" in failed(plan)
    assert "sideways or up" in plan.failures[0].detail


def test_fifty_percent_drop_is_noted_as_stronger():
    plan = screen(limit_price=58.0, bid=57.0, ask=59.0)
    assert plan.approved
    assert any("stronger setup" in n for n in plan.notes)


def test_must_expire_at_least_a_year_out():
    plan = screen(expiration=date(2027, 6, 18))
    assert failed(plan) == ["expires at least 365 days out"]


def test_puts_are_not_covered():
    assert failed(screen(option_type="put")) == ["a call, not a put"]


def test_must_know_why_it_dropped():
    assert failed(screen(checked_why_it_dropped=False)) == ["you know why it dropped"]


def test_stock_must_trade_enough_shares():
    assert failed(screen(underlying_volume=500_000)) == ["stock trades at least 800,000 shares a day"]
    plan = screen(underlying_volume=900_000)
    assert plan.approved and any("low side" in n for n in plan.notes)


def test_no_buying_when_rsi_reaches_seventy():
    assert screen(rsi=66).approved
    assert failed(screen(rsi=70)) == ["RSI below 70"]


def test_never_pay_over_the_ask():
    assert failed(screen(limit_price=71.5)) == ["limit order at or under the ask"]
    assert screen(limit_price=71.0).approved


def test_limit_under_the_bid_is_allowed_but_flagged():
    plan = screen(limit_price=66.0)
    assert plan.approved and any("may not fill" in n for n in plan.notes)


def test_cost_must_be_money_you_can_lose():
    assert failed(screen(contracts=2)) == ["cost is money you are prepared to lose"]  # $14,000


def test_trade_count_for_the_year():
    assert screen(trades_this_year=19).approved
    assert failed(screen(trades_this_year=20)) == ["no more than 20 trades a year"]


def test_later_expiration_on_the_chain_is_pointed_out():
    plan = screen(furthest_expiration=date(2029, 1, 19))
    assert plan.approved and any("furthest expiration" in n for n in plan.notes)


def test_rules_can_be_tightened():
    strict = LongCallRules(min_contract_drop=0.50)
    assert not screen(rules=strict).approved


@pytest.mark.parametrize(
    "overrides",
    [dict(bid=72.0), dict(contracts=0), dict(rsi=140), dict(limit_price=0), dict(contract_high=-1)],
)
def test_bad_inputs_raise(overrides):
    with pytest.raises(ValueError):
        screen(**overrides)
