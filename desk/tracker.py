"""Daily scorecard: how the account did each day against the two targets.

Mirrors the worksheet tracker. The trader records the account's net worth at
the close of each trading day (so gains include open positions), plus any
money added or withdrawn that day. Deposits are never counted as gains, and
both target lines move up by the deposit so the comparison stays fair.

* 1% target      - compounds: yesterday's target line times 1.01.
* $1k/day target - straight line: yesterday's target line plus $1,000.
"""

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional

from .rules import DEFAULT_RULES, Rulebook


@dataclass(frozen=True)
class DayEntry:
    day: date
    balance: float
    deposit: float = 0.0  # money added (+) or withdrawn (-) that day


@dataclass(frozen=True)
class DayScore:
    day: date
    balance: float
    capital: float  # total money put in so far
    daily_gain: float
    daily_pct: float
    total_gain: float
    total_pct: float
    pct_target: float
    pct_target_delta: float
    dollar_target: float
    dollar_target_delta: float
    made_daily_pct: bool  # did this one day gain at least the daily percent goal


def score_days(
    starting_capital: float,
    entries: Iterable[DayEntry],
    rules: Rulebook = DEFAULT_RULES,
) -> List[DayScore]:
    if starting_capital <= 0:
        raise ValueError("starting capital must be positive")

    scores: List[DayScore] = []
    prev_balance = starting_capital
    capital = starting_capital
    pct_target = starting_capital
    dollar_target = starting_capital
    prev_day: Optional[date] = None

    for e in entries:
        if prev_day is not None and e.day <= prev_day:
            raise ValueError(f"entries must be in date order; {e.day} follows {prev_day}")
        prev_day = e.day

        capital += e.deposit
        daily_gain = e.balance - prev_balance - e.deposit
        daily_pct = daily_gain / prev_balance if prev_balance else 0.0
        pct_target = pct_target * (1 + rules.daily_target_pct) + e.deposit
        dollar_target = dollar_target + rules.daily_target_dollars + e.deposit
        total_gain = e.balance - capital

        scores.append(DayScore(
            day=e.day,
            balance=round(e.balance, 2),
            capital=round(capital, 2),
            daily_gain=round(daily_gain, 2),
            daily_pct=round(daily_pct, 6),
            total_gain=round(total_gain, 2),
            total_pct=round(total_gain / capital, 6) if capital else 0.0,
            pct_target=round(pct_target, 2),
            pct_target_delta=round(e.balance - pct_target, 2),
            dollar_target=round(dollar_target, 2),
            dollar_target_delta=round(e.balance - dollar_target, 2),
            made_daily_pct=daily_pct >= rules.daily_target_pct,
        ))
        prev_balance = e.balance

    return scores
