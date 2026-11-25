"""Reading Schwab's data format, and the two web endpoints end to end."""

from datetime import date, datetime, timezone

import pytest

from desk.schwab import DataError, SchwabData, parse_calls, parse_candles
from tests import sample_market as sample


def _ms(day):
    return int(datetime(day.year, day.month, day.day, 6, tzinfo=timezone.utc).timestamp() * 1000)


def price_history_payload(candles):
    return {"symbol": "XYZ", "empty": False, "candles": [
        {"open": c.open, "high": c.high, "low": c.low, "close": c.close, "volume": c.volume,
         "datetime": _ms(c.day)} for c in candles]}


def chain_payload(quotes, today):
    by_expiry = {}
    for q in quotes:
        key = f"{q.expiration.isoformat()}:{(q.expiration - today).days}"
        row = {"putCall": "CALL", "symbol": q.symbol, "bid": q.bid, "ask": q.ask, "mark": q.mark,
               "totalVolume": q.volume, "openInterest": q.open_interest, "strikePrice": q.strike}
        if q.high_52w:
            row["high52Week"] = q.high_52w
        by_expiry.setdefault(key, {}).setdefault(f"{q.strike:.1f}", []).append(row)
    return {"symbol": "XYZ", "status": "SUCCESS", "callExpDateMap": by_expiry, "putExpDateMap": {}}


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status

    def json(self):
        return self._payload


class FakeHttp:
    """Stands in for `requests`, answering from the sample chart."""

    def __init__(self, candles, status=200):
        self.candles, self.status, self.calls = candles, status, []

    def get(self, url, headers=None, params=None, timeout=None):
        self.calls.append((url, headers, params))
        if self.status != 200:
            return FakeResponse({}, self.status)
        if url.endswith("/pricehistory"):
            return FakeResponse(price_history_payload(self.candles))
        today = self.candles[-1].day
        start, end = date.fromisoformat(params["fromDate"]), date.fromisoformat(params["toDate"])
        quotes = [q for q in sample.call_chain(today, self.candles[-1].close) if start <= q.expiration <= end]
        return FakeResponse(chain_payload(quotes, today))


def test_candles_round_trip():
    candles = sample.between_levels()
    assert parse_candles(price_history_payload(candles)) == candles
    assert parse_candles({"candles": []}) == []


def test_calls_round_trip():
    today = date(2026, 6, 1)
    quotes = sample.call_chain(today, 100.0)
    parsed = parse_calls(chain_payload(quotes, today))
    assert sorted(parsed, key=lambda q: q.symbol) == sorted(quotes, key=lambda q: q.symbol)
    assert parse_calls({}) == []


def test_client_sends_the_token_and_reads_candles():
    http = FakeHttp(sample.between_levels())
    candles = SchwabData(lambda: "tok123", http=http).daily_candles("xyz")
    url, headers, params = http.calls[0]
    assert url.endswith("/marketdata/v1/pricehistory")
    assert headers == {"Authorization": "Bearer tok123"}
    assert params["symbol"] == "XYZ" and params["frequencyType"] == "daily"
    assert len(candles) == len(sample.between_levels())


def test_client_explains_a_missing_or_rejected_login():
    with pytest.raises(DataError, match="Not logged in"):
        SchwabData(lambda: None, http=FakeHttp([])).daily_candles("XYZ")
    with pytest.raises(DataError, match="Sign in again"):
        SchwabData(lambda: "old", http=FakeHttp(sample.between_levels(), status=401)).daily_candles("XYZ")
    with pytest.raises(DataError, match="returned 500"):
        SchwabData(lambda: "tok", http=FakeHttp(sample.between_levels(), status=500)).daily_candles("XYZ")


@pytest.fixture
def client(monkeypatch):
    flask_app = pytest.importorskip("app")
    http = FakeHttp(sample.back_at_the_zone())
    monkeypatch.setattr(flask_app, "SchwabData", lambda get_token: SchwabData(lambda: "tok", http=http))
    monkeypatch.delenv("DESK_KEY", raising=False)
    monkeypatch.setenv("DESK_WATCHLIST", "AAA,BBB")
    return flask_app.app.test_client()


def test_guide_endpoint(client):
    res = client.get("/guide/xyz?loss=250&budget=2000")
    body = res.get_json()
    assert res.status_code == 200 and body["ticker"] == "XYZ"
    assert body["zone_method"]["status"] == "at_buyer_zone"
    assert body["zone_method"]["plan"]["max_loss"] <= 250
    assert body["long_call_method"]["far_dated"]  # chain was fetched and read


def test_daily_endpoint_uses_the_watchlist(client):
    body = client.get("/daily").get_json()
    assert [s["ticker"] for s in body["stocks_at_a_buyer_zone"]] == ["AAA", "BBB"]
    body = client.get("/daily?tickers=zzz").get_json()
    assert [s["ticker"] for s in body["stocks_at_a_buyer_zone"]] == ["ZZZ"]


def test_endpoints_can_be_locked_with_a_key(client, monkeypatch):
    monkeypatch.setenv("DESK_KEY", "s3cret")
    assert client.get("/guide/xyz").status_code == 403
    assert client.get("/daily").status_code == 403
    assert client.get("/guide/xyz?key=s3cret").status_code == 200


def test_guide_endpoint_reports_a_lost_login(monkeypatch):
    flask_app = pytest.importorskip("app")
    monkeypatch.setattr(flask_app, "SchwabData", lambda get_token: SchwabData(lambda: None, http=FakeHttp([])))
    monkeypatch.delenv("DESK_KEY", raising=False)
    res = flask_app.app.test_client().get("/guide/xyz")
    assert res.status_code == 502 and "Not logged in" in res.get_json()["error"]
