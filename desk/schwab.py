"""Market data from the Schwab API: daily candles and call option chains.

The caller supplies `get_token`, a function that returns a valid access
token (app.py already keeps one fresh). Nothing here stores credentials.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

from .market import Candle, OptionQuote

BASE_URL = "https://api.schwabapi.com/marketdata/v1"


class DataError(Exception):
    """Market data could not be fetched or read."""


def parse_candles(payload: Dict) -> List[Candle]:
    out = []
    for row in payload.get("candles") or []:
        day = datetime.fromtimestamp(row["datetime"] / 1000, tz=timezone.utc).date()
        out.append(Candle(day, float(row["open"]), float(row["high"]), float(row["low"]),
                          float(row["close"]), int(row.get("volume") or 0)))
    return sorted(out, key=lambda c: c.day)


def parse_calls(payload: Dict) -> List[OptionQuote]:
    out = []
    for expiry_key, strikes in (payload.get("callExpDateMap") or {}).items():
        expiration = date.fromisoformat(expiry_key.split(":")[0])
        for contracts in strikes.values():
            for c in contracts:
                high = c.get("high52Week")
                out.append(OptionQuote(
                    symbol=c.get("symbol", ""),
                    option_type="call",
                    strike=float(c["strikePrice"]),
                    expiration=expiration,
                    bid=float(c.get("bid") or 0),
                    ask=float(c.get("ask") or 0),
                    mark=float(c.get("mark") or 0),
                    volume=int(c.get("totalVolume") or 0),
                    open_interest=int(c.get("openInterest") or 0),
                    high_52w=float(high) if high else None,
                ))
    return out


class SchwabData:
    def __init__(self, get_token: Callable[[], Optional[str]], http=None, timeout: int = 20):
        if http is None:
            import requests as http  # only needed when talking to the real API
        self._get_token, self._http, self._timeout = get_token, http, timeout

    def _get(self, path: str, params: Dict) -> Dict:
        token = self._get_token()
        if not token:
            raise DataError("Not logged in to Schwab. Open the app's home page and sign in again.")
        res = self._http.get(f"{BASE_URL}{path}", headers={"Authorization": f"Bearer {token}"},
                             params=params, timeout=self._timeout)
        if res.status_code == 401:
            raise DataError("Schwab rejected the login. Sign in again.")
        if res.status_code != 200:
            raise DataError(f"Schwab returned {res.status_code} for {path}.")
        return res.json()

    def daily_candles(self, symbol: str, years: int = 2) -> List[Candle]:
        payload = self._get("/pricehistory", {
            "symbol": symbol.upper(), "periodType": "year", "period": years,
            "frequencyType": "daily", "frequency": 1,
        })
        candles = parse_candles(payload)
        if not candles:
            raise DataError(f"No price history for {symbol.upper()}.")
        return candles

    def _calls(self, symbol: str, start: date, end: date) -> List[OptionQuote]:
        payload = self._get("/chains", {
            "symbol": symbol.upper(), "contractType": "CALL", "strategy": "SINGLE", "range": "OTM",
            "fromDate": start.isoformat(), "toDate": end.isoformat(),
        })
        return parse_calls(payload)

    def calls(self, symbol: str, today: Optional[date] = None) -> List[OptionQuote]:
        """Out-of-the-money calls: the far-dated ones plus the six-week window."""
        today = today or date.today()
        far = self._calls(symbol, today + timedelta(days=365), today + timedelta(days=1200))
        near = self._calls(symbol, today + timedelta(days=20), today + timedelta(days=70))
        return far + near
