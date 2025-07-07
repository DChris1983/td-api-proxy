from flask import Flask, request, redirect
import requests
import urllib.parse
import base64
import os
import json
import time

app = Flask(__name__)

# Schwab OAuth config
CLIENT_ID = "o6TGb5qdKXKy8arRAGpWwrvKR6AeZhTh"
CLIENT_SECRET = os.environ.get("SCHWAB_CLIENT_SECRET", "YOUR_SECRET_HERE")
REDIRECT_URI = "https://td-api-proxy.onrender.com/callback"
AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
OPTION_CHAIN_URL = "https://api.schwabapi.com/marketdata/v1/chains"
TOKEN_FILE = "token.json"

@app.route("/")
def login():
    auth_params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI
    }
    return redirect(AUTH_URL + "?" + urllib.parse.urlencode(auth_params))

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "No code received."

    basic_auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {basic_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }

    res = requests.post(TOKEN_URL, headers=headers, data=urllib.parse.urlencode(token_data))
    if res.status_code == 200:
        token = res.json()
        token["timestamp"] = int(time.time())
        with open(TOKEN_FILE, "w") as f:
            json.dump(token, f)
        return "Token saved. You're authenticated!"
    return f"Token error: {res.text}"

def get_valid_token():
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, "r") as f:
        token = json.load(f)

    now = int(time.time())
    expires_in = token.get("expires_in", 1800)
    issued_at = token.get("timestamp", now)
    refresh_token = token.get("refresh_token")

    if now - issued_at > expires_in - 60 and refresh_token:
        basic_auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        headers = {
            "Authorization": f"Basic {basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "redirect_uri": REDIRECT_URI
        }

        res = requests.post(TOKEN_URL, headers=headers, data=urllib.parse.urlencode(refresh_data))
        if res.status_code == 200:
            new_token = res.json()
            new_token["timestamp"] = int(time.time())
            new_token["refresh_token"] = refresh_token
            with open(TOKEN_FILE, "w") as f:
                json.dump(new_token, f)
            return new_token["access_token"]
        else:
            print("Refresh failed:", res.text)
            return None

    return token.get("access_token")

@app.route("/scan")
def scan():
    max_cost = float(request.args.get("maxCost", 8))
    access_token = get_valid_token()

    if not access_token:
        return {"error": "No valid token. Please authenticate."}, 401

    headers = {"Authorization": f"Bearer {access_token}"}
    tickers = ["AAPL", "TSLA", "AMD", "NVDA", "SOFI", "DKNG", "MSFT", "GOOGL", "META"]
    viable = []

    for ticker in tickers:
        params = {
            "symbol": ticker,
            "contractType": "ALL",
            "strategy": "SINGLE",
            "includeQuotes": "TRUE",
            "range": "NTM",
            "strikeCount": 10
        }

        try:
            res = requests.get(OPTION_CHAIN_URL, headers=headers, params=params)
            if res.status_code != 200:
                continue

            data = res.json()
            calls = data.get("callExpDateMap", {})
            puts = data.get("putExpDateMap", {})

            def has_cheap_options(opt_map):
                for exp in opt_map.values():
                    for strike, opts in exp.items():
                        for o in opts:
                            if o.get("ask") and o["ask"] <= max_cost and o.get("totalVolume", 0) > 100:
                                return True
                return False

            if has_cheap_options(calls) or has_cheap_options(puts):
                viable.append(ticker)

        except Exception as e:
            print(f"{ticker} scan error:", e)

    return {"tickers": viable}

@app.route("/option-chain")
def option_chain():
    ticker = request.args.get("ticker")
    if not ticker:
        return {"error": "Missing ticker"}, 400

    access_token = get_valid_token()
    if not access_token:
        return {"error": "No valid token"}, 401

    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "symbol": ticker,
        "contractType": "ALL",
        "strategy": "SINGLE",
        "includeQuotes": "TRUE",
        "range": "NTM",
        "strikeCount": 20
    }

    res = requests.get(OPTION_CHAIN_URL, headers=headers, params=params)
    return res.json(), res.status_code

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
