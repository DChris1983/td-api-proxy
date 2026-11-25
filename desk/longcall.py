"""Long-dated call checklist: is this contract worth buying, and at what price?

The method: buy calls on strong, heavily traded companies, dated as far out
as the option chain goes so that time can absorb a correction, and only
after the contract itself has fallen 40% or more from where it was trading.
Enter with a limit order and never chase the ask. Trade rarely.

Buying a call can lose everything paid for it, so the most this trade can
lose is its full cost. The checklist makes you say up front that the cost
is money you are prepared to lose.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from .rules import DEFAULT_LONG_CALL_RULES, LongCallRules
from .tradeplan import Check

SHARES_PER_CONTRACT = 100


@dataclass(frozen=True)
class LongCallPlan:
    ticker: str
    strike: float
    expiration: date
    days_to_expiration: int
    limit_price: float
    contracts: int
    cost: float  # also the most this trade can lose
    contract_drop: float  # fall from the contract's earlier price, 0.42 = 42%
    trailing_stops: List[float] = field(default_factory=list)
    checks: List[Check] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    @property
    def approved(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> List[Check]:
        return [c for c in self.checks if not c.passed]


def screen_long_call(
    ticker: str,
    strike: float,
    expiration: date,
    contract_high: float,
    bid: float,
    ask: float,
    limit_price: float,
    underlying_volume: int,
    rsi: float,
    money_prepared_to_lose: float,
    checked_why_it_dropped: bool,
    contracts: int = 1,
    option_type: str = "call",
    today: Optional[date] = None,
    furthest_expiration: Optional[date] = None,
    trades_this_year: Optional[int] = None,
    rules: LongCallRules = DEFAULT_LONG_CALL_RULES,
) -> LongCallPlan:
    """Run one option contract through the checklist.

    contract_high   - the price the contract was trading at before it fell
    bid, ask        - the contract's current quote, per share
    limit_price     - the price you intend to put on the limit order
    underlying_volume - shares of the stock traded on a typical day
    rsi             - the stock's 14-day RSI
    checked_why_it_dropped - you looked at the news, the last earnings
                      report, volume and open interest for the reason
    """
    today = today or date.today()
    if min(strike, contract_high, ask, limit_price, money_prepared_to_lose) <= 0 or bid < 0:
        raise ValueError("prices and the budget must be positive")
    if bid > ask:
        raise ValueError(f"bid {bid} is above ask {ask}")
    if contracts < 1:
        raise ValueError("at least one contract")
    if not 0 <= rsi <= 100:
        raise ValueError("RSI runs from 0 to 100")

    kind = option_type.strip().lower()
    dte = (expiration - today).days
    drop = (contract_high - limit_price) / contract_high
    cost = limit_price * SHARES_PER_CONTRACT * contracts
    checks: List[Check] = []
    notes: List[str] = []

    checks.append(Check(
        "a call, not a put",
        kind == "call",
        "far-dated buys are calls only" if kind == "call"
        else "puts are kept short-dated; this checklist only covers far-dated calls",
    ))
    checks.append(Check(
        f"expires at least {rules.min_days_to_expiration} days out",
        dte >= rules.min_days_to_expiration,
        f"{dte} days to expiration" if dte >= 0 else "this contract has already expired",
    ))
    checks.append(Check(
        f"contract is down at least {rules.min_contract_drop:.0%}",
        drop >= rules.min_contract_drop,
        f"down {drop:.0%} from {contract_high:,.2f}" if drop > 0
        else "the contract has gone sideways or up, not down",
    ))
    checks.append(Check(
        "you know why it dropped",
        checked_why_it_dropped,
        "news, earnings, volume and open interest checked" if checked_why_it_dropped
        else "check the news, the last earnings report, volume and open interest first",
    ))
    checks.append(Check(
        f"stock trades at least {rules.min_underlying_volume:,} shares a day",
        underlying_volume >= rules.min_underlying_volume,
        f"{underlying_volume:,} shares a day",
    ))
    checks.append(Check(
        f"RSI below {rules.max_rsi_to_buy:g}",
        rsi < rules.max_rsi_to_buy,
        f"RSI is {rsi:g}" + ("" if rsi < rules.max_rsi_to_buy else ": getting overbought, not a time to buy"),
    ))
    checks.append(Check(
        "limit order at or under the ask",
        limit_price <= ask,
        f"limit {limit_price:,.2f} against bid {bid:,.2f} / ask {ask:,.2f}" if limit_price <= ask
        else f"limit {limit_price:,.2f} is above the ask of {ask:,.2f}: never pay over the ask",
    ))
    checks.append(Check(
        "cost is money you are prepared to lose",
        cost <= money_prepared_to_lose,
        f"${cost:,.2f} for {contracts} contract{'s' if contracts != 1 else ''} "
        f"against ${money_prepared_to_lose:,.2f}",
    ))
    if trades_this_year is not None:
        checks.append(Check(
            f"no more than {rules.max_trades_per_year} trades a year",
            trades_this_year < rules.max_trades_per_year,
            f"this would be trade {trades_this_year + 1} of the year",
        ))

    if drop >= rules.strong_contract_drop:
        notes.append(f"Down {drop:.0%}: a drop of {rules.strong_contract_drop:.0%} or more is the stronger setup.")
    if furthest_expiration is not None and furthest_expiration > expiration:
        notes.append(
            f"The chain goes out to {furthest_expiration.isoformat()}. "
            "The method takes the furthest expiration listed."
        )
    if rules.min_underlying_volume <= underlying_volume < rules.preferred_underlying_volume:
        notes.append(f"Volume is on the low side; {rules.preferred_underlying_volume:,} a day is preferred.")
    if limit_price < bid:
        notes.append("The limit is under the bid, so it may not fill.")

    return LongCallPlan(
        ticker=ticker.upper(),
        strike=strike,
        expiration=expiration,
        days_to_expiration=dte,
        limit_price=round(limit_price, 2),
        contracts=contracts,
        cost=round(cost, 2),
        contract_drop=round(drop, 4),
        trailing_stops=[round(limit_price * (1 - pct), 2) for pct in rules.trailing_stop_pcts],
        checks=checks,
        notes=notes,
    )
