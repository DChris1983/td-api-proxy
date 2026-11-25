"""The rulebooks: every number the desk enforces, in one place.

Two methods live side by side:

* Rulebook      - the zone method (buyer and seller zones on stocks).
* LongCallRules - the long-dated call method (buying beaten-down calls
                  with a year or more until expiration).

Every value comes from the trader's own course worksheets, study aids and
class notes. Nothing here is a guess. Rules those sources leave open (max
open positions, when to stop for the day) stay unset until confirmed.
"""

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Rulebook:
    # A trade must offer at least this much reward for each dollar risked.
    min_reward_risk: float = 3.0

    # Zone trades: the stop sits beyond the far edge of the entry zone by this
    # fraction of the stock's average daily move (daily Average True Range).
    zone_stop_buffer_adm: float = 0.20

    # Trend / gap trades: the stop sits this many ATRs away from the entry.
    trend_stop_atr_multiple: float = 1.5

    # Odds enhancers: four questions about the zone, 0 to 2 points each.
    # At or above `odds_take_trade`: limit order at the zone's near line.
    # At or above `odds_confirmation`: wait for price to turn in the zone.
    # Below that: skip the zone and find the next one.
    odds_take_trade: int = 7
    odds_confirmation: int = 5

    # No new trade this many days either side of the earnings date.
    earnings_blackout_days: int = 3

    # Daily scorecard targets the tracker measures against.
    daily_target_pct: float = 0.01
    daily_target_dollars: float = 1000.0

    # Not yet sourced. None means "no rule enforced yet".
    max_open_positions: Optional[int] = None
    max_trades_per_day: Optional[int] = None
    max_daily_loss: Optional[float] = None


@dataclass(frozen=True)
class LongCallRules:
    # Only buy a contract whose own price has fallen at least this far from
    # where it was trading. A deeper drop is better.
    min_contract_drop: float = 0.40
    strong_contract_drop: float = 0.50

    # Far-dated means past a year out; further is better.
    min_days_to_expiration: int = 365

    # The stock itself must trade enough shares a day to get in and out.
    min_underlying_volume: int = 800_000
    preferred_underlying_volume: int = 1_000_000

    # Not a time to buy once the 14-day RSI reaches this level.
    max_rsi_to_buy: float = 70.0

    # A calculated handful of trades a year, not a daily habit.
    max_trades_per_year: int = 20

    # Trailing stop distances suggested for anyone new to options.
    trailing_stop_pcts: Tuple[float, ...] = (0.10, 0.20)


DEFAULT_RULES = Rulebook()
DEFAULT_LONG_CALL_RULES = LongCallRules()
