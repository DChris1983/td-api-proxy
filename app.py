from flask import Flask, request, redirect
import requests
import pkce
import urllib.parse
import os

app = Flask(__name__)

# 🔐 Schwab App Credentials
CLIENT_ID = "o6TGb5qdKKKy8arRAGpWwvrKR6AeZhTh"  # Corrected App Key from your screenshot
REDIRECT_URI = "https://td-api-proxy.onrender.com/callback"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"

# 🔒 PKCE (Proof Key for Code Exchange)
code_verifier, code_challenge = pkce.generate_pkce_pair()


@app.route("/")
def login():
    auth_params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256"
    }
    auth_link = AUTH_URL + "?" + urllib.parse.urlencode(auth_params)
    return redirect(auth_link)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "No authorization code received."

    print("Authorization Code:", code, flush=True)

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": code_verifier
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(TOKEN_URL, headers=headers, data=token_data)

    print("\n--- TOKEN EXCHANGE RESPONSE ---", flush=True)
    print("Status Code:", response.status_code, flush=True)
    print("Response Body:", response.text, flush=True)

    return "Token exchange complete. Check terminal output."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
