# td-api-proxy

Two pieces live here.

## `app.py`: Schwab login and market data proxy

Flask app that handles the Schwab OAuth login and exposes option chain
lookups (`/scan`, `/option-chain`). Needs `SCHWAB_CLIENT_SECRET` in the
environment.

## `desk/`: the trading desk rules engine

Pure Python, no dependencies. It takes levels you have already charted and
tells you whether the trade fits the plan, how many shares to buy, and where
the stop and target go. It also scores each day against the daily targets.

```
python -m desk zone HD long --buyer 141.98 141.29 --seller 149.94 148.93 --adm 2.21 --loss 250
python -m desk trend ETSY long --entry 112.50 --target 130 --atr 6.45 --loss 100
```

The exit code is 0 when the trade passes every check and 1 when it does not.

| File | What it does |
| --- | --- |
| `desk/rules.py` | Every number the desk enforces, in one place |
| `desk/tradeplan.py` | Entry, stop, target, reward to risk, share size, pass or fail |
| `desk/tracker.py` | Daily scorecard against the 1% and $1k a day targets |

Run the tests with `python -m pytest`.

This is a planning and discipline tool. It does not place orders and it is
not financial advice.
