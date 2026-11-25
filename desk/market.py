"""Market data shapes and the indicators both methods read off a chart."""

from dataclasses import dataclass
from datetime import date
from typing import List, Optional, Sequence


@dataclass(frozen=True)
class Candle:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: int

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_top(self) -> float:
        return max(self.open, self.close)

    @property
    def body_bottom(self) -> float:
        return min(self.open, self.close)

    @property
    def is_up(self) -> bool:
        return self.close > self.open


@dataclass(frozen=True)
class OptionQuote:
    symbol: str
    option_type: str  # "call" or "put"
    strike: float
    expiration: date
    bid: float
    ask: float
    mark: float
    volume: int
    open_interest: int
    high_52w: Optional[float] = None  # contract's own 52-week high, when the feed has it


def sma(values: Sequence[float], length: int) -> Optional[float]:
    if len(values) < length:
        return None
    return sum(values[-length:]) / length


def rsi(closes: Sequence[float], length: int = 14) -> Optional[float]:
    """Wilder's Relative Strength Index, the version charting sites show."""
    if len(closes) <= length:
        return None
    changes = [b - a for a, b in zip(closes, closes[1:])]
    gain = sum(c for c in changes[:length] if c > 0) / length
    loss = sum(-c for c in changes[:length] if c < 0) / length
    for c in changes[length:]:
        gain = (gain * (length - 1) + max(c, 0)) / length
        loss = (loss * (length - 1) + max(-c, 0)) / length
    if loss == 0:
        return 100.0
    return 100 - 100 / (1 + gain / loss)


def true_ranges(candles: Sequence[Candle]) -> List[float]:
    out = []
    for prev, cur in zip(candles, candles[1:]):
        out.append(max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close)))
    return out


def atr(candles: Sequence[Candle], length: int = 14) -> Optional[float]:
    """Wilder's Average True Range: the stock's average daily move."""
    trs = true_ranges(candles)
    if len(trs) < length:
        return None
    value = sum(trs[:length]) / length
    for tr in trs[length:]:
        value = (value * (length - 1) + tr) / length
    return value


def average_volume(candles: Sequence[Candle], length: int = 30) -> Optional[float]:
    if not candles:
        return None
    recent = candles[-length:]
    return sum(c.volume for c in recent) / len(recent)
