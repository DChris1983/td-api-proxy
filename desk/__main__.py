"""Command line: check a charted setup against the rules.

    python -m desk zone HD long --buyer 141.98 141.29 --seller 149.94 148.93 --adm 2.21 --loss 250
    python -m desk trend ETSY long --entry 112.50 --target 130 --atr 6.45 --loss 100
"""

import argparse
import sys

from .tradeplan import Zone, plan_trend_trade, plan_zone_trade


def _print_plan(plan) -> None:
    verdict = "TAKE IT - fits the plan" if plan.approved else "SKIP IT - does not fit the plan"
    print(f"{plan.ticker}  {plan.direction} {plan.kind} trade   ->   {verdict}")
    print(f"  entry   ${plan.entry:>10,.2f}")
    print(f"  stop    ${plan.stop:>10,.2f}   (risk  ${plan.risk_per_share:,.2f} a share)")
    print(f"  target  ${plan.target:>10,.2f}   (reward ${plan.reward_per_share:,.2f} a share)")
    print(f"  reward to risk  {plan.reward_risk:.2f}:1")
    print(f"  shares  {plan.shares:,}   cost ${plan.cost:,.2f}")
    print(f"  if stopped out  -${plan.max_loss:,.2f}     at target  +${plan.profit_at_target:,.2f}")
    for c in plan.checks:
        print(f"  [{'ok' if c.passed else 'NO'}] {c.name}: {c.detail}")


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

    trend = sub.add_parser("trend", help="trend or gap trade with an ATR stop")
    trend.add_argument("ticker")
    trend.add_argument("direction", choices=["long", "short"])
    trend.add_argument("--entry", type=float, required=True)
    trend.add_argument("--target", type=float, required=True)
    trend.add_argument("--atr", type=float, required=True)
    trend.add_argument("--loss", type=float, required=True, help="dollars you are willing to lose")

    args = parser.parse_args(argv)
    try:
        if args.kind == "zone":
            plan = plan_zone_trade(
                args.ticker, args.direction,
                Zone(*args.buyer), Zone(*args.seller),
                args.adm, args.loss,
            )
        else:
            plan = plan_trend_trade(
                args.ticker, args.direction, args.entry, args.target, args.atr, args.loss,
            )
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    _print_plan(plan)
    return 0 if plan.approved else 1


if __name__ == "__main__":
    sys.exit(main())
