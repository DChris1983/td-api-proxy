"""The guide: put in a stock, get told what to do under each method.

`build_guide` takes a year of daily candles (and, when available, the call
options chain) and returns a plain dictionary ready to show or send:

* zone method      - where the nearest buyer and seller zones are, whether
                     price is at one, and the full trade plan if it is.
* long call method - whether the stock passes the checks, and which
                     far-dated calls are priced favorably right now.

`build_daily_report` runs the guide over a watchlist and puts the names
that stand out at the top.
"""

import math
from dataclasses import dataclass
from datetime import date
from typing import Callable, Dict, Iterable, List, Optional, Sequence

from .longcall import screen_long_call
from .market import Candle, OptionQuote, atr, average_volume, rsi, sma
from .odds import CONFIRMATION_ENTRY
from .rules import DEFAULT_LONG_CALL_RULES, DEFAULT_RULES, LongCallRules, Rulebook
from .tradeplan import plan_zone_trade
from .zones import DEFAULT_ZONE_SETTINGS, ZoneSettings, find_zones, nearest_buyer_zone, nearest_seller_zone

# Strike distances taken from the class examples, as a share above the stock
# price: the far-dated call was about 26% above, the short-dated swing call
# 8 to 9% above and about six weeks from expiring.
EXAMPLE_FAR_STRIKE = 0.26
EXAMPLE_SWING_STRIKE = 0.085
EXAMPLE_SWING_DAYS = 42


@dataclass(frozen=True)
class GuideSettings:
    loss_threshold: float = 100.0  # dollars risked on one stock trade
    option_budget: float = 1000.0  # dollars you are prepared to lose on one options trade
    at_zone_within: float = 0.5  # "at the zone" = within this many average daily moves of it
    max_strike_above: float = 0.40  # furthest strike listed, as a share above the stock price
    max_candidates: int = 6
    rules: Rulebook = DEFAULT_RULES
    call_rules: LongCallRules = DEFAULT_LONG_CALL_RULES
    zone_settings: ZoneSettings = DEFAULT_ZONE_SETTINGS


DEFAULT_GUIDE_SETTINGS = GuideSettings()


def _r(value, places=2):
    return None if value is None else round(value, places)


def _zone_dict(z):
    return None if z is None else {
        "near_line": z.proximal, "far_line": z.distal, "formed": z.formed.isoformat(),
        "base_candles": z.base_candles, "leg_out": z.leg_out, "revisits": z.revisits,
    }


def _zone_method(ticker, price, move, candles, settings, days_to_earnings) -> Dict:
    zones = find_zones(candles, settings.zone_settings)
    buyer = nearest_buyer_zone(zones, price)
    seller = nearest_seller_zone(zones, price)
    out = {"buyer_zone": _zone_dict(buyer), "seller_zone": _zone_dict(seller), "plan": None, "standout": False}

    if buyer is None:
        out.update(status="no_buyer_zone",
                   action="No buyer zone found below the price in the last year. Nothing to do here.")
        return out
    if seller is None:
        out.update(status="no_seller_zone",
                   action="No seller zone above the price, so there is no target to measure reward "
                          "against. The method does not buy at all-time highs.")
        return out
    if seller.proximal <= buyer.proximal:
        out.update(status="zones_overlap",
                   action="The nearest buyer and seller zones overlap. Chart this one by hand.")
        return out

    plan = plan_zone_trade(
        ticker, "long", buyer.zone, seller.zone, move, settings.loss_threshold,
        rules=settings.rules, entry_zone_quality=buyer.quality, days_to_earnings=days_to_earnings,
    )
    out["plan"] = {
        "entry": plan.entry, "stop": plan.stop, "target": plan.target,
        "reward_risk": plan.reward_risk, "shares": plan.shares, "cost": plan.cost,
        "max_loss": plan.max_loss, "profit_at_target": plan.profit_at_target,
        "odds_score": plan.odds.total, "entry_type": plan.entry_type,
        "passes": plan.approved, "fails": [f"{c.name}: {c.detail}" for c in plan.failures],
    }
    out["distance_to_entry_pct"] = _r((price - plan.entry) / price * 100, 1)

    reach = settings.at_zone_within * move
    orders = (f"buy limit {plan.entry:,.2f}, stop market {plan.stop:,.2f}, "
              f"sell limit {plan.target:,.2f}, {plan.shares} shares")
    if price <= buyer.proximal + reach:
        if not plan.approved:
            out.update(status="at_buyer_zone_fails",
                       action="Price is at a buyer zone, but the trade does not fit the plan: "
                              + "; ".join(out["plan"]["fails"]) + ".")
        elif plan.entry_type == CONFIRMATION_ENTRY:
            out.update(status="at_buyer_zone", standout=True,
                       action=f"Price is at a buyer zone that scores {plan.odds.total} of 8. Do not buy at "
                              "the line. Watch it go into the zone and buy only once it turns back up. "
                              f"Plan: {orders}.")
        else:
            out.update(status="at_buyer_zone", standout=True,
                       action=f"Price is at a buyer zone that scores {plan.odds.total} of 8. {orders.capitalize()}.")
    elif price >= seller.proximal - reach:
        out.update(status="at_seller_zone",
                   action="Price is at a seller zone. Not a place to buy. If you own it, this is the target area.")
    elif plan.approved:
        out.update(status="between_levels",
                   action=f"Between levels, so wait. Set an alert at {plan.entry:,.2f} "
                          f"({out['distance_to_entry_pct']}% below). The setup there fits the plan: {orders}.")
    else:
        out.update(status="between_levels",
                   action="Between levels, so wait. The buyer zone below does not fit the plan as it stands: "
                          + "; ".join(out["plan"]["fails"]) + ".")
    return out


def _candidate(ticker, price, q: OptionQuote, stock_volume, stock_rsi, settings, today) -> Dict:
    limit = round((q.bid + q.ask) / 2, 2) if q.bid > 0 else q.ask
    cost = round(limit * 100, 2)
    row = {
        "symbol": q.symbol, "strike": q.strike, "expiration": q.expiration.isoformat(),
        "days_left": (q.expiration - today).days,
        "strike_above_price_pct": _r((q.strike - price) / price * 100, 1),
        "bid": q.bid, "ask": q.ask, "limit_price": limit, "cost_per_contract": cost,
        "contracts_within_budget": math.floor(settings.option_budget / cost) if cost > 0 else 0,
        "open_interest": q.open_interest, "volume": q.volume,
        "drop_from_high_pct": None, "favorable": False,
    }
    if limit <= 0 or q.ask <= 0:
        row["verdict"] = "No live quote on this contract."
        return row
    if not q.high_52w:
        row["verdict"] = "The feed has no price history for this contract. Check its chart for a 40% drop."
        return row
    plan = screen_long_call(
        ticker, q.strike, q.expiration, q.high_52w, q.bid, q.ask, limit,
        int(stock_volume), stock_rsi, settings.option_budget, True,
        today=today, rules=settings.call_rules,
    )
    row["drop_from_high_pct"] = _r(plan.contract_drop * 100, 0)
    row["favorable"] = plan.approved
    row["verdict"] = ("Favorably priced: passes every automatic check." if plan.approved
                      else "; ".join(f"{c.name}: {c.detail}" for c in plan.failures) + ".")
    return row


def _closest(rows: List[Dict], target_pct: float) -> Optional[Dict]:
    return min(rows, key=lambda r: abs(r["strike_above_price_pct"] - target_pct)) if rows else None


def _long_call_method(ticker, price, closes, volume, stock_rsi, calls, settings, today) -> Dict:
    r = settings.call_rules
    checks = [
        {"name": f"stock trades at least {r.min_underlying_volume:,} shares a day",
         "passed": volume >= r.min_underlying_volume, "detail": f"{volume:,.0f} a day on average"},
        {"name": f"RSI below {r.max_rsi_to_buy:g}",
         "passed": stock_rsi < r.max_rsi_to_buy, "detail": f"RSI is {stock_rsi:.0f}"},
    ]
    notes = []
    fifty = sma(closes, 50)
    if fifty:
        gap = (price - fifty) / fifty * 100
        notes.append(f"Price is {abs(gap):.1f}% {'above' if gap >= 0 else 'below'} the 50-day average "
                     f"({fifty:,.2f}), the line watched for a bounce.")
    out = {"stock_checks": checks, "notes": notes, "far_dated": [], "swing_example": None, "standout": False}
    stock_ok = all(c["passed"] for c in checks)

    if not calls:
        out["action"] = ("No option chain loaded. " if stock_ok else "The stock fails the checks above. ") + \
            "Connect market data to see which calls are priced favorably."
        return out

    in_range = [q for q in calls if q.option_type == "call"
                and price <= q.strike <= price * (1 + settings.max_strike_above)]
    far = [q for q in in_range if (q.expiration - today).days >= r.min_days_to_expiration]
    if far:
        furthest = max(q.expiration for q in far)
        rows = [_candidate(ticker, price, q, volume, stock_rsi, settings, today)
                for q in sorted(far, key=lambda q: q.strike) if q.expiration == furthest]
        match = _closest(rows, EXAMPLE_FAR_STRIKE * 100)
        if match:
            match["like_class_example"] = "Closest to the class example: a strike about 26% above the stock."
        rows.sort(key=lambda row: (not row["favorable"], abs(row["strike_above_price_pct"] - EXAMPLE_FAR_STRIKE * 100)))
        out["far_dated"] = rows[:settings.max_candidates]
        out["furthest_expiration"] = furthest.isoformat()

    swing = [q for q in in_range if 20 <= (q.expiration - today).days <= 70]
    if swing:
        expiry = min({q.expiration for q in swing}, key=lambda d: abs((d - today).days - EXAMPLE_SWING_DAYS))
        rows = [_candidate(ticker, price, q, volume, stock_rsi, settings, today)
                for q in swing if q.expiration == expiry]
        pick = _closest(rows, EXAMPLE_SWING_STRIKE * 100)
        if pick:
            pick["verdict"] = ("Short-dated swing in the style of the class example: a strike 8 to 9% above "
                               "the stock, about six weeks out, cheap enough to buy several. Only worth it "
                               "ahead of a catalyst you can name, and only if the strike is reachable in time.")
            out["swing_example"] = pick

    good = [row for row in out["far_dated"] if row["favorable"]]
    if not stock_ok:
        out["action"] = "The stock fails the checks above, so no calls here for now."
    elif good:
        best = good[0]
        out["standout"] = True
        out["action"] = (
            f"{len(good)} far-dated call{'s' if len(good) != 1 else ''} priced favorably. Closest to the class "
            f"example: the {best['strike']:g} strike expiring {best['expiration']}, down "
            f"{best['drop_from_high_pct']:.0f}% from its high, about ${best['cost_per_contract']:,.0f} a contract. "
            f"Use a limit order near {best['limit_price']:,.2f} and never above the ask of {best['ask']:,.2f}. "
            "Before buying, check the news, the last earnings report, volume and open interest for why it dropped.")
    elif out["far_dated"]:
        out["action"] = "No far-dated call is down 40% from its high right now. Nothing to buy; check back."
    else:
        out["action"] = "No calls listed a year or more out for this stock."
    return out


def build_guide(
    ticker: str,
    candles: Sequence[Candle],
    calls: Optional[Sequence[OptionQuote]] = None,
    settings: GuideSettings = DEFAULT_GUIDE_SETTINGS,
    today: Optional[date] = None,
    days_to_earnings: Optional[int] = None,
) -> Dict:
    ticker = ticker.upper()
    candles = sorted(candles, key=lambda c: c.day)
    if len(candles) < 60:
        return {"ticker": ticker, "error": "Not enough price history (need at least 60 trading days)."}

    today = today or candles[-1].day
    closes = [c.close for c in candles]
    price, move, stock_rsi = closes[-1], atr(candles), rsi(closes)
    volume = average_volume(candles)

    zone = _zone_method(ticker, price, move, candles, settings, days_to_earnings)
    call = _long_call_method(ticker, price, closes, volume, stock_rsi, calls, settings, today)
    return {
        "ticker": ticker,
        "as_of": candles[-1].day.isoformat(),
        "price": _r(price),
        "snapshot": {
            "average_daily_move": _r(move), "rsi_14": _r(stock_rsi, 0), "average_volume": int(volume),
            "sma_50": _r(sma(closes, 50)), "sma_100": _r(sma(closes, 100)), "sma_200": _r(sma(closes, 200)),
        },
        "zone_method": zone,
        "long_call_method": call,
        "standout": zone["standout"] or call["standout"],
    }


def build_daily_report(
    tickers: Iterable[str],
    fetch_guide: Callable[[str], Dict],
) -> Dict:
    """Run the guide over a watchlist. `fetch_guide` returns one guide per ticker."""
    stock_setups, call_setups, alerts, quiet, errors = [], [], [], [], []
    for ticker in tickers:
        try:
            g = fetch_guide(ticker)
        except Exception as err:  # one bad ticker must not sink the list
            errors.append({"ticker": ticker.upper(), "error": str(err)})
            continue
        if g.get("error"):
            errors.append({"ticker": g["ticker"], "error": g["error"]})
            continue
        zone, call = g["zone_method"], g["long_call_method"]
        line = {"ticker": g["ticker"], "price": g["price"]}
        if zone["standout"]:
            stock_setups.append({**line, "action": zone["action"], "plan": zone["plan"]})
        elif zone.get("status") == "between_levels" and zone["plan"] and zone["plan"]["passes"]:
            alerts.append({**line, "alert_at": zone["plan"]["entry"],
                           "percent_away": zone["distance_to_entry_pct"], "action": zone["action"]})
        if call["standout"]:
            call_setups.append({**line, "action": call["action"],
                                "contracts": [c for c in call["far_dated"] if c["favorable"]]})
        if not g["standout"]:
            quiet.append(g["ticker"])
    alerts.sort(key=lambda a: a["percent_away"])
    return {
        "stocks_at_a_buyer_zone": stock_setups,
        "calls_priced_favorably": call_setups,
        "alerts_to_set": alerts,
        "nothing_today": quiet,
        "errors": errors,
    }
