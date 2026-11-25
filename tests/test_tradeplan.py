"""The engine must reproduce the worksheet model, row for row."""

import pytest

from desk import Rulebook, Zone, plan_trend_trade, plan_zone_trade

# (ticker, buyer high, buyer low, seller high, seller low, ADM, loss threshold,
#  expected stop, reward, risk, passes 3:1, whole shares)
WORKSHEET_LONGS = [
    ("HD", 141.98, 141.29, 149.94, 148.93, 2.21, 250, 140.85, 6.95, 1.13, True, 220),
    ("ZM", 253.90, 248.24, 278.22, 271.87, 12.15, 250, 245.81, 17.97, 8.09, False, 30),
    ("MAR", 83.54, 80.36, 100.06, 97.87, 3.03, 350, 79.75, 14.33, 3.79, True, 92),
    ("GOOG", 1483.00, 1466.00, 1570.69, 1558.63, 37.74, 500, 1458.45, 75.63, 24.55, True, 20),
    ("SPOT", 254.96, 246.00, 299.86, 289.59, 13.53, 200, 243.29, 34.63, 11.67, False, 17),
    ("CMG", 1102.66, 1067.19, 1185.15, 1161.46, 29.57, 50, 1061.28, 58.80, 41.38, False, 1),
]


@pytest.mark.parametrize(
    "ticker,bz_hi,bz_lo,sz_hi,sz_lo,adm,loss,stop,reward,risk,passes,shares", WORKSHEET_LONGS
)
def test_long_zone_trade_matches_worksheet(
    ticker, bz_hi, bz_lo, sz_hi, sz_lo, adm, loss, stop, reward, risk, passes, shares
):
    plan = plan_zone_trade(ticker, "long", Zone(bz_hi, bz_lo), Zone(sz_hi, sz_lo), adm, loss)

    assert plan.entry == bz_hi  # top line of the buyer zone
    assert plan.target == sz_lo  # bottom line of the seller zone
    assert plan.stop == pytest.approx(stop, abs=0.011)
    assert plan.reward_per_share == pytest.approx(reward, abs=0.011)
    assert plan.risk_per_share == pytest.approx(risk, abs=0.011)
    assert plan.approved is passes
    assert plan.shares == shares
    assert plan.max_loss <= loss


def test_short_zone_trade_mirrors_the_long():
    plan = plan_zone_trade("XYZ", "short", Zone(100, 98), Zone(121, 120), 2.5, 300)

    assert plan.entry == 120  # bottom line of the seller zone
    assert plan.target == 100  # top line of the buyer zone
    assert plan.stop == 121.5  # seller zone high + 20% of ADM
    assert plan.risk_per_share == 1.5
    assert plan.reward_per_share == 20
    assert plan.shares == 200
    assert plan.approved


def test_exactly_three_to_one_passes():
    # entry 100, stop 99 (zone low 99.2 less 20% of an ADM of 1), target 103
    plan = plan_zone_trade("XYZ", "long", Zone(100, 99.2), Zone(105, 103), 1.0, 100)
    assert plan.reward_risk == 3.0
    assert plan.approved


def test_rejects_when_one_share_risks_more_than_the_threshold():
    plan = plan_zone_trade(
        "CMG", "long", Zone(1102.66, 1067.19), Zone(1185.15, 1161.46), 29.57, 35
    )
    assert plan.shares == 0
    assert not plan.approved
    assert "position size fits the loss threshold" in [c.name for c in plan.failures]


def test_rejects_overlapping_zones():
    plan = plan_zone_trade("XYZ", "long", Zone(100, 98), Zone(101, 99.5), 1.0, 100)
    assert not plan.approved
    assert "seller zone sits above buyer zone" in [c.name for c in plan.failures]


def test_trend_long_uses_atr_stop():
    plan = plan_trend_trade("ETSY", "long", 112.50, 130.00, 6.45, 100)
    assert plan.stop == pytest.approx(102.825, abs=0.006)  # 1.5 x ATR below entry
    assert plan.reward_per_share == 17.5
    assert plan.shares == 10
    assert not plan.approved  # 1.81:1


def test_trend_short_uses_atr_stop():
    plan = plan_trend_trade("CRM", "short", 255.00, 216.00, 14.69, 300)
    assert plan.stop == pytest.approx(277.035, abs=0.006)  # 1.5 x ATR above entry
    assert plan.reward_per_share == 39
    assert plan.shares == 13
    assert not plan.approved  # 1.77:1


def test_rulebook_can_be_tightened():
    strict = Rulebook(min_reward_risk=4.0)
    plan = plan_zone_trade(
        "MAR", "long", Zone(83.54, 80.36), Zone(100.06, 97.87), 3.03, 350, rules=strict
    )
    assert plan.reward_risk == pytest.approx(3.78, abs=0.01)
    assert not plan.approved


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(direction="sideways"),
        dict(avg_daily_move=0),
        dict(loss_threshold=0),
    ],
)
def test_bad_inputs_raise(kwargs):
    args = dict(
        ticker="XYZ", direction="long", buyer_zone=Zone(100, 98), seller_zone=Zone(121, 120),
        avg_daily_move=2.5, loss_threshold=300,
    )
    args.update(kwargs)
    with pytest.raises(ValueError):
        plan_zone_trade(**args)


def test_zone_lines_must_be_in_order():
    with pytest.raises(ValueError):
        Zone(high=98, low=100)
