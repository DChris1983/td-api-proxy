from flask import Flask, request, redirect, session
import requests
import urllib.parse
import base64
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "supersecretkey")

# ✅ Schwab App credentials (set secret in Render)
CLIENT_ID = "o6TGb5qdKXKy8arRAGpWwrvKR6AeZhTh"
CLIENT_SECRET = os.environ.get("SCHWAB_CLIENT_SECRET", "YOUR_SECRET_HERE")
REDIRECT_URI = "https://td-api-proxy.onrender.com/callback"
AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
OPTION_CHAIN_URL = "https://api.schwabapi.com/marketdata/v1/chains"

@app.route("/")
def login():
    auth_params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI
    }

    auth_link = AUTH_URL + "?" + urllib.parse.urlencode(auth_params)
    return redirect(auth_link)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "No authorization code received."

    auth_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
    basic_auth = base64.b64encode(auth_string.encode()).decode()

    headers = {
        "Authorization": f"Basic {basic_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }

    encoded_data = urllib.parse.urlencode(token_data)
    response = requests.post(TOKEN_URL, headers=headers, data=encoded_data)

    if response.status_code == 200:
        session["access_token"] = response.json().get("access_token")
        return "Token exchange complete. You're authenticated!"
    else:
        return f"Error getting token: {response.text}"

def get_access_token():
    return session.get("access_token")

@app.route("/scan")
def scan():
    max_cost = float(request.args.get("maxCost", 8))
    access_token = get_access_token()

    if not access_token:
        return {"error": "No access token. Authenticate via root (/) first."}, 401

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

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
            response = requests.get(OPTION_CHAIN_URL, headers=headers, params=params)
            if response.status_code != 200:
                print(f"Failed on {ticker}: {response.text}")
                continue

            data = response.json()
            calls = data.get("callExpDateMap", {})
            puts = data.get("putExpDateMap", {})

            def extract_prices(option_map):
                for exp in option_map.values():
                    for strike, options in exp.items():
                        for opt in options:
                            ask = opt.get("ask")
                            vol = opt.get("totalVolume", 0)
                            if ask is not None and ask <= max_cost and vol > 100:
                                return True
                return False

            if extract_prices(calls) or extract_prices(puts):
                viable.append(ticker)

        except Exception as e:
            print(f"Error scanning {ticker}: {e}")
            continue

    return {"tickers": viable}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
