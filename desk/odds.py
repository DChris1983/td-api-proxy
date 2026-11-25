"""Odds enhancers: four questions that grade how strong a zone is.

Each question earns 0, 1 or 2 points, for a total out of 8.

1. Reward to risk     3:1 or better = 2,  2:1 = 1,  less = 0
2. How it left        long candle = 2,    medium = 1,  small = 0
3. Time in the zone   1-2 base candles = 2,  3-4 = 1,  5 or more = 0
4. Freshness          never revisited = 2,  once = 1,  twice or more = 0

Only the base candles count for time in the zone. The candle that leaves
the zone is judged for speed and is never counted as a base candle or as a
revisit. A wick touching the zone counts as a revisit.

The total decides what to do at the zone. For the zone you enter at:
7-8 take the trade with a limit order at the near line, 5-6 wait for price
to go into the zone and turn, 4 or less skip it. For the zone you are
aiming at: 7-8 get out just before it, 5-6 watch for a turn inside it,
4 or less expect price to ride through.
"""

from dataclasses import dataclass

from .rules import DEFAULT_RULES, Rulebook

LEG_OUT_POINTS = {"long": 2, "medium": 1, "small": 0}

LIMIT_ENTRY = "limit entry at the near line"
CONFIRMATION_ENTRY = "confirmation entry"
SKIP_ZONE = "skip this zone"

EXIT_BEFORE_ZONE = "sell just before the zone"
WATCH_FOR_TURN = "watch for a turn inside the zone"
RIDE_THROUGH = "expect price to ride through"


@dataclass(frozen=True)
class ZoneQuality:
    """What the trader reads off the chart for one zone."""

    leg_out: str  # "long", "medium" or "small" candle leaving the zone
    base_candles: int  # candles in the base
    revisits: int  # times price has come back to the zone since

    def __post_init__(self):
        if self.leg_out.strip().lower() not in LEG_OUT_POINTS:
            raise ValueError("leg out must be 'long', 'medium' or 'small'")
        if self.base_candles < 1:
            raise ValueError("a zone has at least one base candle")
        if self.revisits < 0:
            raise ValueError("revisits cannot be negative")


@dataclass(frozen=True)
class OddsScore:
    reward_risk: int
    leg_out: int
    time_in_zone: int
    freshness: int

    @property
    def total(self) -> int:
        return self.reward_risk + self.leg_out + self.time_in_zone + self.freshness

    def breakdown(self) -> str:
        return (
            f"reward to risk {self.reward_risk} + leg out {self.leg_out} + "
            f"time in zone {self.time_in_zone} + freshness {self.freshness}"
        )


def reward_risk_points(ratio: float) -> int:
    # The study aids score 3:1 and 2:1 and say nothing between 1:1 and 2:1;
    # anything under 2:1 is scored 0 here.
    if ratio >= 3:
        return 2
    if ratio >= 2:
        return 1
    return 0


def time_in_zone_points(base_candles: int) -> int:
    if base_candles <= 2:
        return 2
    if base_candles <= 4:
        return 1
    return 0


def freshness_points(revisits: int) -> int:
    if revisits == 0:
        return 2
    if revisits == 1:
        return 1
    return 0


def score_zone(reward_risk_ratio: float, quality: ZoneQuality) -> OddsScore:
    return OddsScore(
        reward_risk=reward_risk_points(reward_risk_ratio),
        leg_out=LEG_OUT_POINTS[quality.leg_out.strip().lower()],
        time_in_zone=time_in_zone_points(quality.base_candles),
        freshness=freshness_points(quality.revisits),
    )


def entry_action(total: int, rules: Rulebook = DEFAULT_RULES) -> str:
    """What to do at the zone you want to enter at."""
    if total >= rules.odds_take_trade:
        return LIMIT_ENTRY
    if total >= rules.odds_confirmation:
        return CONFIRMATION_ENTRY
    return SKIP_ZONE


def exit_action(total: int, rules: Rulebook = DEFAULT_RULES) -> str:
    """What to expect at the zone you are aiming for."""
    if total >= rules.odds_take_trade:
        return EXIT_BEFORE_ZONE
    if total >= rules.odds_confirmation:
        return WATCH_FOR_TURN
    return RIDE_THROUGH
