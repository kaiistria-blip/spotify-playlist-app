import os
import json
from flask import Flask, request
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from main import run_playlist_builder

app = Flask(__name__)

# ===== CONFIG =====
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI")
SCOPE = "user-top-read playlist-modify-private playlist-modify-public user-library-read"

TOKEN_DIR = "tokens"

# ===== OAUTH =====
def get_oauth():
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        open_browser=False
    )

# ===== HOME =====
@app.route("/")
def home():
    auth_url = get_oauth().get_authorize_url()
    return f'<a href="{auth_url}">Login with Spotify</a>'

# ===== CALLBACK =====
@app.route("/callback")
def callback():
    try:
        code = request.args.get("code")
        sp_oauth = get_oauth()

        token_info = sp_oauth.get_access_token(code)

        os.makedirs(TOKEN_DIR, exist_ok=True)

        sp = spotipy.Spotify(auth=token_info["access_token"])
        user_id = sp.current_user()["id"]

        with open(f"{TOKEN_DIR}/{user_id}.json", "w") as f:
            json.dump(token_info, f)

        print(f"Saved token for {user_id}")

        run_playlist_builder(sp)

        return f"Playlist updated for {user_id}"

    except Exception as e:
        print("CALLBACK ERROR:", e)
        return str(e)

# ===== RUN ALL USERS =====
def run_all_users():
    if not os.path.exists(TOKEN_DIR):
        print("No token directory")
        return

    files = os.listdir(TOKEN_DIR)

    if not files:
        print("No users found")
        return

    for file in files:
        if not file.endswith(".json"):
            continue

        path = f"{TOKEN_DIR}/{file}"

        try:
            with open(path, "r") as f:
                token_info = json.load(f)

            # 🔥 CRITICAL: refresh token
            sp_oauth = get_oauth()
            token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])

            # save refreshed token
            with open(path, "w") as f:
                json.dump(token_info, f)

            sp = spotipy.Spotify(auth=token_info["access_token"])

            run_playlist_builder(sp)

            print(f"Updated: {file}")

        except Exception as e:
            print(f"FAILED: {file} -> {e}")

# ===== ROUTE =====
@app.route("/run_all")
def run_all():
    print("RUN_ALL TRIGGERED")
    run_all_users()
    return "Updated all users"

# ===== START =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
