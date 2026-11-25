"""A hand-built daily chart with one seller zone above and one buyer zone below."""

from datetime import date, timedelta

from desk.market import Candle, OptionQuote

START = date(2026, 1, 5)


def _candles(moves, volume=2_000_000):
    out, day = [], START
    for open_, close in moves:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        out.append(Candle(day, open_, max(open_, close) + 0.4, min(open_, close) - 0.4, close, volume))
        day += timedelta(days=1)
    return out


def _steps(start, end, size):
    moves, price = [], start
    while abs(end - price) > 1e-9:
        nxt = price + size if end > price else price - size
        moves.append((price, nxt))
        price = nxt
    return moves


FLAT = [(100.0, 100.2), (100.2, 100.0)] * 35           # 70 quiet days around 100
RALLY = _steps(100.0, 110.0, 2.0)                       # up to 110
TOP_BASE = [(110.0, 110.2), (110.2, 110.0)]             # two small candles
DROP = [(110.0, 107.5)] + _steps(107.5, 95.5, 2.0)      # long candle down, then lower
LOW_BASE = [(95.5, 95.3), (95.3, 95.5)]                 # two small candles
BOUNCE = [(95.5, 98.0), (98.0, 99.5)]                   # long candle up
DRIFT = [(99.5, 99.7), (99.7, 99.5)] * 3                # six quiet days

BETWEEN_LEVELS = FLAT + RALLY + TOP_BASE + DROP + LOW_BASE + BOUNCE + DRIFT
BACK_AT_THE_ZONE = BETWEEN_LEVELS + [(99.5, 97.7), (97.7, 96.0)]
ALL_TIME_HIGH = FLAT + RALLY


def between_levels():
    return _candles(BETWEEN_LEVELS)


def back_at_the_zone():
    return _candles(BACK_AT_THE_ZONE)


def all_time_high():
    return _candles(ALL_TIME_HIGH)


def call_chain(today, price):
    """Far-dated strikes with one contract down 45%, plus a six-week expiration."""
    far = today + timedelta(days=760)
    nearer = today + timedelta(days=400)
    swing = today + timedelta(days=44)
    q = lambda strike, exp, bid, ask, high: OptionQuote(  # noqa: E731
        f"XYZ {exp:%y%m%d}C{strike:g}", "call", strike, exp, bid, ask, (bid + ask) / 2, 150, 4200, high)
    return [
        q(round(price * 1.05), far, 17.8, 18.2, 20.0),    # down 10%
        q(round(price * 1.15), far, 13.0, 13.4, 16.0),    # down 17.5%
        q(round(price * 1.25), far, 5.4, 5.6, 10.0),      # down 45%: favorable
        q(round(price * 1.35), far, 4.0, 4.2, None),      # no price history in the feed
        q(round(price * 1.25), nearer, 2.0, 2.2, 5.0),    # down 58% but not the furthest date
        q(round(price * 1.05), swing, 1.1, 1.3, 2.0),
        q(round(price * 1.085), swing, 0.6, 0.8, 1.5),
        q(round(price * 1.15), swing, 0.2, 0.3, 0.9),
    ]
