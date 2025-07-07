from flask import Flask, request, redirect, session
import requests
import pkce
import urllib.parse
import base64
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "supersecretkey")

# ✅ Schwab credentials and endpoints
CLIENT_ID = "o6TGb5qdKXKy8arRAGpWwrvKR6AeZhTh"
REDIRECT_URI = "https://td-api-proxy.onrender.com/callback"
AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"

@app.route("/")
def login():
    code_verifier, code_challenge = pkce.generate_pkce_pair()
    session["code_verifier"] = code_verifier

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

    code_verifier = session.get("code_verifier")
    if not code_verifier:
        return "Missing code_verifier. Restart the login process."

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": code_verifier
    }

    # 🔐 Encode client_id as Basic Auth (client_id + ":")
    basic_auth = base64.b64encode(f"{CLIENT_ID}:".encode()).decode()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {basic_auth}"
    }

    encoded_data = urllib.parse.urlencode(token_data)
    response = requests.post(TOKEN_URL, headers=headers, data=encoded_data)

    print("\n--- TOKEN EXCHANGE RESPONSE ---", flush=True)
    print("Status Code:", response.status_code, flush=True)
    print("Response Body:", response.text, flush=True)

    return "Token exchange complete. Check terminal output."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
