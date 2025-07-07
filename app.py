from flask import Flask, request, redirect, session
import requests
import urllib.parse
import base64
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "supersecretkey")

# ✅ Use your actual Schwab App credentials
CLIENT_ID = "o6TGb5qdKXKy8arRAGpWwrvKR6AeZhTh"
CLIENT_SECRET = os.environ.get("SCHWAB_CLIENT_SECRET", "YOUR_SECRET_HERE")  # Set this in Render
REDIRECT_URI = "https://td-api-proxy.onrender.com/callback"
AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"

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

    # 🛡️ Basic Auth header: base64(client_id:client_secret)
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

    print("\n--- TOKEN EXCHANGE RESPONSE ---", flush=True)
    print("Status Code:", response.status_code, flush=True)
    print("Response Body:", response.text, flush=True)

    return "Token exchange complete. Check terminal output."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
