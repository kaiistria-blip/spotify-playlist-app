from flask import Flask, request
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
import os

from main import run_playlist_builder

if not os.path.exists("tokens"):
    os.makedirs("tokens")

app = Flask(__name__)

CLIENT_ID = "3098f91adf5547ecb3214339a0e8bd51"
CLIENT_SECRET = "a646012b50ad4fdd8218192ecec29632"
REDIRECT_URI = "https://spotify-playlist-app-ntpf.onrender.com/callback"

SCOPE = "playlist-modify-public playlist-modify-private playlist-read-private user-top-read playlist-read-collaborative"

def get_oauth():
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        open_browser=False
    )

@app.route("/")
def home():
    auth_url = get_oauth().get_authorize_url()
    return f'<a href="{auth_url}">Login with Spotify</a>'

@app.route("/callback")
def callback():
    code = request.args.get("code")
    sp_oauth = get_oauth()

    # 🔴 STEP 1: get token
    token_info = sp_oauth.get_access_token(code)

    # 🔴 STEP 2: save token (simple version)
    os.makedirs("tokens", exist_ok=True)

    sp = spotipy.Spotify(auth=token_info["access_token"])
    user = sp.current_user()["id"]

    with open(f"tokens/{user}.json", "w") as f:
        json.dump(token_info, f)

    # 🔴 STEP 3: create Spotify client
    sp = spotipy.Spotify(auth=token_info["access_token"])
    user = sp.current_user()["id"]

    # 🔴 STEP 4: run your playlist system
    run_playlist_builder(sp)

    return f"Playlist updated successfully for {user}"

def run_all_users():
    for file in os.listdir("tokens"):
        if not file.endswith(".json"):
            continue

        path = f"tokens/{file}"

        # skip empty files
        if os.path.getsize(path) == 0:
            print(f"Skipping empty file: {file}")
            continue

        try:
            with open(path, "r") as f:
                token_info = json.load(f)
        except Exception as e:
            print(f"Skipping invalid JSON: {file} ({e})")
            continue

        sp = spotipy.Spotify(auth=token_info["access_token"])

        try:
            run_playlist_builder(sp)
            print(f"Updated: {file}")
        except Exception as e:
            print(f"Failed for {file}: {e}")

is_running = False

@app.route("/run_all", methods=["GET"])
def run_all():
    global is_running

    print("RUN_ALL TRIGGERED")

    if is_running:
        print("Already running — skipping")
        return "Already running"

    is_running = True

    try:
        run_all_users()
    finally:
        is_running = False

    return "Updated all users"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
