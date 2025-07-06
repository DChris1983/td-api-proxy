from flask import Flask, request, redirect
import requests
import pkce
import webbrowser
import urllib.parse

app = Flask(__name__)

# 🔐 Replace this with your actual Schwab App Key (Client ID)
CLIENT_ID = "o6TGb5qdKXKy8arRAGpWwrvKR6AeZhTh"
REDIRECT_URI = "REDIRECT_URI = "http://localhost:5000/callback"
"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"

# PKCE: one-time secure values
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

    print("Authorization Code:", code)

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "code_verifier": code_verifier
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(TOKEN_URL, headers=headers, data=token_data)

    print("\n--- TOKEN EXCHANGE RESPONSE ---")
    print("Status Code:", response.status_code)
    print("Response Body:", response.text)

    return "Token exchange complete. Check terminal output."

if __name__ == "__main__":
    webbrowser.open("http://localhost:5000")
    app.run(port=5000)
