"""Command line: check a setup against the rules before you take it.

    python -m desk zone HD long --buyer 141.98 141.29 --seller 149.94 148.93 --adm 2.21 --loss 250
    python -m desk zone HD long ... --leg-out long --base 2 --revisits 0 --earnings-in 12
    python -m desk trend ETSY long --entry 112.50 --target 130 --atr 6.45 --loss 100
    python -m desk longcall META --strike 600 --expires 2028-12-15 --high 120 --bid 68 --ask 71
        --limit 70 --volume 15000000 --rsi 55 --budget 8000 --checked-news
"""

import argparse
import sys
from datetime import date

from .longcall import screen_long_call
from .odds import ZoneQuality
from .tradeplan import Zone, plan_trend_trade, plan_zone_trade

TAKE = "TAKE IT - fits the plan"
SKIP = "SKIP IT - does not fit the plan"


def _print_checks(checks) -> None:
    for c in checks:
        print(f"  [{'ok' if c.passed else 'NO'}] {c.name}: {c.detail}")


def _print_plan(plan) -> None:
    print(f"{plan.ticker}  {plan.direction} {plan.kind} trade   ->   {TAKE if plan.approved else SKIP}")
    print(f"  entry   ${plan.entry:>10,.2f}")
    print(f"  stop    ${plan.stop:>10,.2f}   (risk  ${plan.risk_per_share:,.2f} a share)")
    print(f"  target  ${plan.target:>10,.2f}   (reward ${plan.reward_per_share:,.2f} a share)")
    print(f"  reward to risk  {plan.reward_risk:.2f}:1")
    print(f"  shares  {plan.shares:,}   cost ${plan.cost:,.2f}")
    print(f"  if stopped out  -${plan.max_loss:,.2f}     at target  +${plan.profit_at_target:,.2f}")
    if plan.entry_type:
        print(f"  how to enter    {plan.entry_type}")
    _print_checks(plan.checks)


def _print_long_call(plan) -> None:
    print(f"{plan.ticker}  {plan.strike:g} call, expires {plan.expiration.isoformat()}"
          f"   ->   {TAKE if plan.approved else SKIP}")
    print(f"  limit price     ${plan.limit_price:,.2f} a share, {plan.contracts} contract"
          f"{'s' if plan.contracts != 1 else ''}")
    print(f"  cost            ${plan.cost:,.2f}   (this is also the most you can lose)")
    print(f"  contract drop   {plan.contract_drop:.0%}")
    print(f"  time left       {plan.days_to_expiration} days")
    stops = ", ".join(f"${s:,.2f}" for s in plan.trailing_stops)
    print(f"  trailing stops  {stops}   (10% and 20% under your price)")
    _print_checks(plan.checks)
    for note in plan.notes:
        print(f"  note: {note}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m desk", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="kind", required=True)

    zone = sub.add_parser("zone", help="trade between a buyer zone and a seller zone")
    zone.add_argument("ticker")
    zone.add_argument("direction", choices=["long", "short"])
    zone.add_argument("--buyer", nargs=2, type=float, required=True, metavar=("HIGH", "LOW"))
    zone.add_argument("--seller", nargs=2, type=float, required=True, metavar=("HIGH", "LOW"))
    zone.add_argument("--adm", type=float, required=True, help="average daily move (daily ATR)")
    zone.add_argument("--loss", type=float, required=True, help="dollars you are willing to lose")
    zone.add_argument("--leg-out", choices=["long", "medium", "small"],
                      help="size of the candle that left the zone you enter at")
    zone.add_argument("--base", type=int, help="number of base candles in that zone")
    zone.add_argument("--revisits", type=int, help="times price has come back to that zone")
    zone.add_argument("--earnings-in", type=int, metavar="DAYS",
                      help="days until earnings (negative for days since)")

    trend = sub.add_parser("trend", help="trend or gap trade with an ATR stop")
    trend.add_argument("ticker")
    trend.add_argument("direction", choices=["long", "short"])
    trend.add_argument("--entry", type=float, required=True)
    trend.add_argument("--target", type=float, required=True)
    trend.add_argument("--atr", type=float, required=True)
    trend.add_argument("--loss", type=float, required=True, help="dollars you are willing to lose")

    call = sub.add_parser("longcall", help="long-dated call on a beaten-down contract")
    call.add_argument("ticker")
    call.add_argument("--strike", type=float, required=True)
    call.add_argument("--expires", type=date.fromisoformat, required=True, metavar="YYYY-MM-DD")
    call.add_argument("--high", type=float, required=True,
                      help="price the contract was trading at before it fell")
    call.add_argument("--bid", type=float, required=True)
    call.add_argument("--ask", type=float, required=True)
    call.add_argument("--limit", type=float, required=True, help="your limit order price")
    call.add_argument("--volume", type=int, required=True, help="shares the stock trades a day")
    call.add_argument("--rsi", type=float, required=True, help="the stock's 14-day RSI")
    call.add_argument("--budget", type=float, required=True,
                      help="dollars you are prepared to lose on this trade")
    call.add_argument("--contracts", type=int, default=1)
    call.add_argument("--type", choices=["call", "put"], default="call")
    call.add_argument("--checked-news", action="store_true",
                      help="you checked news, earnings, volume and open interest for the drop")
    call.add_argument("--furthest", type=date.fromisoformat, metavar="YYYY-MM-DD",
                      help="the furthest expiration the chain lists")
    call.add_argument("--trades-this-year", type=int)
    call.add_argument("--today", type=date.fromisoformat, metavar="YYYY-MM-DD", help=argparse.SUPPRESS)

    args = parser.parse_args(argv)
    try:
        if args.kind == "zone":
            graded = [args.leg_out, args.base, args.revisits]
            if any(v is not None for v in graded) and any(v is None for v in graded):
                parser.error("--leg-out, --base and --revisits go together")
            quality = ZoneQuality(args.leg_out, args.base, args.revisits) if args.leg_out else None
            plan = plan_zone_trade(
                args.ticker, args.direction,
                Zone(*args.buyer), Zone(*args.seller),
                args.adm, args.loss,
                entry_zone_quality=quality, days_to_earnings=args.earnings_in,
            )
            _print_plan(plan)
        elif args.kind == "trend":
            plan = plan_trend_trade(
                args.ticker, args.direction, args.entry, args.target, args.atr, args.loss,
            )
            _print_plan(plan)
        else:
            plan = screen_long_call(
                args.ticker, args.strike, args.expires, args.high, args.bid, args.ask,
                args.limit, args.volume, args.rsi, args.budget, args.checked_news,
                contracts=args.contracts, option_type=args.type, today=args.today,
                furthest_expiration=args.furthest, trades_this_year=args.trades_this_year,
            )
            _print_long_call(plan)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    return 0 if plan.approved else 1


if __name__ == "__main__":
    sys.exit(main())
