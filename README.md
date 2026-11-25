# td-api-proxy

Two pieces live here.

## `app.py`: Schwab login and market data proxy

Flask app that handles the Schwab OAuth login and exposes option chain
lookups (`/scan`, `/option-chain`). Needs `SCHWAB_CLIENT_SECRET` in the
environment.

## `desk/`: the trading desk rules engine

Pure Python, no dependencies. You bring a setup you have already found; it
tells you whether the trade fits the plan and why. Two methods are built in.

### Zone method (stocks)

Trades between a buyer zone and a seller zone. Returns entry, stop, target,
reward to risk and share count, graded against the rules.

```
python -m desk zone HD long --buyer 141.98 141.29 --seller 149.94 148.93 --adm 2.21 --loss 250
python -m desk trend ETSY long --entry 112.50 --target 130 --atr 6.45 --loss 100
```

Add the odds enhancers and the earnings date to grade the zone itself:

```
python -m desk zone HD long --buyer 141.98 141.29 --seller 149.94 148.93 --adm 2.21 --loss 250 \
    --leg-out long --base 2 --revisits 0 --earnings-in 12
```

A score of 7 or 8 is a limit entry at the zone, 5 or 6 is a confirmation
entry, 4 or less is a skip.

### Long call method (options)

Buying far-dated calls on contracts that have fallen 40% or more.

```
python -m desk longcall META --strike 600 --expires 2028-12-15 --high 120 \
    --bid 68 --ask 71 --limit 70 --volume 15000000 --rsi 55 --budget 8000 --checked-news
```

### Files

| File | What it does |
| --- | --- |
| `desk/rules.py` | Every number both methods enforce, in one place |
| `desk/tradeplan.py` | Zone and trend trades: entry, stop, target, share size, pass or fail |
| `desk/odds.py` | Odds enhancers: the four zone questions and what the score means |
| `desk/longcall.py` | Long call checklist: drop, expiration, volume, RSI, limit price, cost |
| `desk/tracker.py` | Daily scorecard against the 1% and $1k a day targets |

Every command exits 0 when the trade passes every check and 1 when it does
not. Run the tests with `python -m pytest`.

This is a planning and discipline tool. It does not place orders and it is
not financial advice.
