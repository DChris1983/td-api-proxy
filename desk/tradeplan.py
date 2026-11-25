"""Turn charted levels into a trade plan, and say whether it passes the rules.

Two kinds of plan, matching the two blocks of the worksheet model:

* zone trade  - enter at the near edge of a buyer (long) or seller (short)
                zone, stop just past its far edge, target the opposing zone.
* trend trade - entry and target are chosen by hand, stop is ATR based.

Position size always comes from the loss threshold: the dollars the trader
has decided, in advance, they are willing to lose on this one trade.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional

from .odds import SKIP_ZONE, OddsScore, ZoneQuality, entry_action, score_zone
from .rules import DEFAULT_RULES, Rulebook

LONG = "long"
SHORT = "short"


@dataclass(frozen=True)
class Zone:
    """A price zone drawn on the chart, as its upper and lower lines."""

    high: float
    low: float

    def __post_init__(self):
        if self.high <= 0 or self.low <= 0:
            raise ValueError("zone prices must be positive")
        if self.high < self.low:
            raise ValueError(f"zone high {self.high} is below zone low {self.low}")


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class TradePlan:
    ticker: str
    kind: str  # "zone" or "trend"
    direction: str
    entry: float
    stop: float
    target: float
    reward_per_share: float
    risk_per_share: float
    reward_risk: float
    shares: int
    cost: float
    max_loss: float
    profit_at_target: float
    loss_threshold: float
    checks: List[Check] = field(default_factory=list)
    odds: Optional[OddsScore] = None  # set when the zone was graded
    entry_type: Optional[str] = None  # how to enter, from the odds score

    @property
    def approved(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> List[Check]:
        return [c for c in self.checks if not c.passed]


def _direction(value: str) -> str:
    d = value.strip().lower()
    if d not in (LONG, SHORT):
        raise ValueError(f"direction must be 'long' or 'short', got {value!r}")
    return d


def _finish(ticker, kind, direction, entry, stop, target, loss_threshold, rules, extra_checks,
            quality=None):
    if loss_threshold <= 0:
        raise ValueError("loss threshold must be a positive dollar amount")

    if direction == LONG:
        reward = target - entry
        risk = entry - stop
    else:
        reward = entry - target
        risk = stop - entry

    checks = list(extra_checks)
    checks.append(Check(
        "stop on the correct side",
        risk > 0,
        f"risk per share is ${risk:,.2f}" if risk > 0
        else "the stop is not on the losing side of the entry",
    ))
    checks.append(Check(
        "target on the correct side",
        reward > 0,
        f"reward per share is ${reward:,.2f}" if reward > 0
        else "the target is not on the winning side of the entry",
    ))

    reward_risk = reward / risk if risk > 0 else 0.0
    checks.append(Check(
        f"reward to risk at least {rules.min_reward_risk:g}:1",
        risk > 0 and reward > 0 and reward_risk >= rules.min_reward_risk,
        f"this trade is {reward_risk:.2f}:1",
    ))

    # Whole shares only, rounded down, so a stop-out never costs more than
    # the threshold. (The worksheet shows a fractional quantity.)
    shares = math.floor(loss_threshold / risk) if risk > 0 else 0
    checks.append(Check(
        "position size fits the loss threshold",
        shares >= 1,
        f"{shares} shares risks ${shares * risk:,.2f} of the ${loss_threshold:,.2f} threshold"
        if shares >= 1
        else f"one share risks ${risk:,.2f}, more than the ${loss_threshold:,.2f} threshold",
    ))

    odds = entry_type = None
    if quality is not None:
        odds = score_zone(reward_risk, quality)
        entry_type = entry_action(odds.total, rules)
        checks.append(Check(
            f"odds enhancers score at least {rules.odds_confirmation} of 8",
            entry_type != SKIP_ZONE,
            f"{odds.total} of 8 ({odds.breakdown()}): {entry_type}",
        ))

    return TradePlan(
        ticker=ticker.upper(),
        kind=kind,
        direction=direction,
        entry=round(entry, 2),
        stop=round(stop, 2),
        target=round(target, 2),
        reward_per_share=round(reward, 2),
        risk_per_share=round(risk, 2),
        reward_risk=round(reward_risk, 2),
        shares=shares,
        cost=round(shares * entry, 2),
        max_loss=round(shares * risk, 2) if risk > 0 else 0.0,
        profit_at_target=round(shares * reward, 2) if reward > 0 else 0.0,
        loss_threshold=loss_threshold,
        checks=checks,
        odds=odds,
        entry_type=entry_type,
    )


def plan_zone_trade(
    ticker: str,
    direction: str,
    buyer_zone: Zone,
    seller_zone: Zone,
    avg_daily_move: float,
    loss_threshold: float,
    rules: Rulebook = DEFAULT_RULES,
    entry_zone_quality: Optional[ZoneQuality] = None,
    days_to_earnings: Optional[int] = None,
) -> TradePlan:
    """Plan a trade between a buyer zone below and a seller zone above.

    Long:  buy at the top line of the buyer zone, sell at the bottom line of
           the seller zone, stop below the buyer zone.
    Short: sell at the bottom line of the seller zone, cover at the top line
           of the buyer zone, stop above the seller zone.

    `entry_zone_quality` grades the zone you enter at with the odds
    enhancers. `days_to_earnings` is the days until the next earnings date
    (negative for days since the last one).
    """
    direction = _direction(direction)
    if avg_daily_move <= 0:
        raise ValueError("average daily move must be positive")

    buffer = rules.zone_stop_buffer_adm * avg_daily_move
    if direction == LONG:
        entry, target = buyer_zone.high, seller_zone.low
        stop = buyer_zone.low - buffer
    else:
        entry, target = seller_zone.low, buyer_zone.high
        stop = seller_zone.high + buffer

    zones_ordered = Check(
        "seller zone sits above buyer zone",
        seller_zone.low > buyer_zone.high,
        f"buyer zone tops out at {buyer_zone.high:,.2f}, seller zone starts at {seller_zone.low:,.2f}",
    )
    checks = [zones_ordered]
    if days_to_earnings is not None:
        window = rules.earnings_blackout_days
        when = (f"earnings in {days_to_earnings} days" if days_to_earnings >= 0
                else f"earnings were {-days_to_earnings} days ago")
        checks.append(Check(
            f"outside the earnings window ({window} days either side)",
            abs(days_to_earnings) > window,
            when,
        ))
    return _finish(ticker, "zone", direction, entry, stop, target, loss_threshold, rules, checks,
                   quality=entry_zone_quality)


def plan_trend_trade(
    ticker: str,
    direction: str,
    entry: float,
    target: float,
    atr: float,
    loss_threshold: float,
    rules: Rulebook = DEFAULT_RULES,
) -> TradePlan:
    """Plan a trend or gap trade: hand-picked entry and target, ATR stop."""
    direction = _direction(direction)
    if entry <= 0 or target <= 0:
        raise ValueError("entry and target must be positive prices")
    if atr <= 0:
        raise ValueError("ATR must be positive")

    distance = rules.trend_stop_atr_multiple * atr
    stop = entry - distance if direction == LONG else entry + distance
    return _finish(ticker, "trend", direction, entry, stop, target, loss_threshold, rules, [])
