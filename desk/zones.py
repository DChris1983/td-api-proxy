"""Find buyer and seller zones on a daily chart.

A zone is a leg in, one or more small base candles, and a leg out.

* Buyer zone:  price leaves upward. Near line = top of the base candle
               bodies. Far line = lowest wick of the base and both legs.
* Seller zone: price leaves downward. Near line = bottom of the base candle
               bodies. Far line = highest wick of the base and both legs.

A zone stays on the chart until price closes beyond its far line. Every
later, separate return into the zone counts as a revisit (a wick is enough).

The course grades the leg out as a long, medium or small candle without
putting numbers on it. The sizes used here are this program's own
yardstick, measured against the average daily move, and can be changed in
ZoneSettings. Treat every zone found here as a proposal to confirm on your
own chart, not as a replacement for charting.
"""

from dataclasses import dataclass
from typing import List, Optional, Sequence

from .market import Candle, atr
from .odds import ZoneQuality
from .tradeplan import Zone

BUYER = "buyer"
SELLER = "seller"


@dataclass(frozen=True)
class ZoneSettings:
    base_body_max: float = 0.5  # base candle body, as a share of the average daily move
    medium_leg_min: float = 0.6  # leg-out size that counts as a medium candle
    long_leg_min: float = 1.0  # leg-out size that counts as a long candle
    max_base_candles: int = 6
    lookback: int = 250  # trading days searched, about a year


DEFAULT_ZONE_SETTINGS = ZoneSettings()


@dataclass(frozen=True)
class FoundZone:
    side: str  # "buyer" or "seller"
    proximal: float  # near line, the one price reaches first
    distal: float  # far line
    formed: object  # date of the leg-out candle
    base_candles: int
    leg_out: str  # "long" or "medium"
    revisits: int

    @property
    def zone(self) -> Zone:
        return Zone(high=max(self.proximal, self.distal), low=min(self.proximal, self.distal))

    @property
    def quality(self) -> ZoneQuality:
        return ZoneQuality(self.leg_out, self.base_candles, self.revisits)


def _leg_size(candles: Sequence[Candle], i: int) -> float:
    """Leg candle's move, counting an opening gap as part of the candle."""
    c = candles[i]
    gap = abs(c.open - candles[i - 1].close) if i > 0 else 0.0
    return c.body + gap


def _revisits_and_alive(side, proximal, distal, later: Sequence[Candle]):
    visits, inside, left = 0, False, False
    for c in later:
        if side == BUYER:
            if c.close < distal:
                return visits, False
            touching = c.low <= proximal
        else:
            if c.close > distal:
                return visits, False
            touching = c.high >= proximal
        if not touching:
            left, inside = True, False
        elif left and not inside:
            visits, inside = visits + 1, True
    return visits, True


def find_zones(candles: Sequence[Candle], settings: ZoneSettings = DEFAULT_ZONE_SETTINGS) -> List[FoundZone]:
    """Every zone still standing, oldest first."""
    candles = list(candles)[-settings.lookback:]
    move = atr(candles)
    if move is None or move <= 0:
        return []

    found: List[FoundZone] = []
    n = len(candles)
    # The leg out must be followed by at least one finished candle.
    for out in range(2, n - 1):
        size = _leg_size(candles, out) / move
        if size < settings.medium_leg_min:
            continue
        leg = candles[out]
        side = BUYER if leg.is_up else SELLER

        start = out
        while (start - 1 >= 1 and out - (start - 1) <= settings.max_base_candles
               and candles[start - 1].body <= settings.base_body_max * move):
            start -= 1
        base = candles[start:out]
        if not base:
            continue
        leg_in = candles[start - 1]
        span = [leg_in] + base + [leg]

        if side == BUYER:
            proximal = max(c.body_top for c in base)
            distal = min(c.low for c in span)
            if leg.close <= proximal:
                continue  # did not actually leave the base
        else:
            proximal = min(c.body_bottom for c in base)
            distal = max(c.high for c in span)
            if leg.close >= proximal:
                continue
        if proximal == distal:
            continue

        revisits, alive = _revisits_and_alive(side, proximal, distal, candles[out + 1:])
        if not alive:
            continue
        found.append(FoundZone(
            side=side,
            proximal=round(proximal, 2),
            distal=round(distal, 2),
            formed=leg.day,
            base_candles=len(base),
            leg_out="long" if size >= settings.long_leg_min else "medium",
            revisits=revisits,
        ))
    return found


def nearest_buyer_zone(zones: Sequence[FoundZone], price: float) -> Optional[FoundZone]:
    """The first buyer zone at or below price. Never skip a closer one."""
    below = [z for z in zones if z.side == BUYER and z.distal <= price]
    return max(below, key=lambda z: z.proximal) if below else None


def nearest_seller_zone(zones: Sequence[FoundZone], price: float) -> Optional[FoundZone]:
    """The first seller zone at or above price."""
    above = [z for z in zones if z.side == SELLER and z.distal >= price]
    return min(above, key=lambda z: z.proximal) if above else None
