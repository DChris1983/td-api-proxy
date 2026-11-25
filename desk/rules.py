"""The rulebook: every number the desk enforces, in one place.

Each value here comes from the trader's own course worksheets (the zone
risk-to-reward model and the daily balance tracker). Nothing in this file is
a guess. Rules the worksheets do not pin down (max open positions, when to
stop for the day, how a zone is scored) are deliberately left unset until
they are confirmed against the course itself.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Rulebook:
    # A trade must offer at least this much reward for each dollar risked.
    min_reward_risk: float = 3.0

    # Zone trades: the stop sits beyond the far edge of the entry zone by this
    # fraction of the stock's average daily move (daily Average True Range).
    zone_stop_buffer_adm: float = 0.20

    # Trend / gap trades: the stop sits this many ATRs away from the entry.
    trend_stop_atr_multiple: float = 1.5

    # Daily scorecard targets the tracker measures against.
    daily_target_pct: float = 0.01
    daily_target_dollars: float = 1000.0

    # Not yet sourced from the course. None means "no rule enforced yet".
    max_open_positions: Optional[int] = None
    max_trades_per_day: Optional[int] = None
    max_daily_loss: Optional[float] = None


DEFAULT_RULES = Rulebook()
