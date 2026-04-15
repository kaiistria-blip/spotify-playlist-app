import random
import json
import os

PLAYLIST_NAME = "Daily Drive (Auto)"

TRACK_MEMORY_FILE = "played_tracks.json"
EP_MEMORY_FILE = "played_episodes.json"

TRACK_MEMORY_SIZE = 200
EP_MEMORY_SIZE = 30

# ===== MEMORY =====
def load_memory(file):
    if os.path.exists(file):
        with open(file, "r") as f:
            return json.load(f)
    return []

def save_memory(file, data, limit):
    with open(file, "w") as f:
        json.dump(data[-limit:], f)

# ===== PLAYLIST =====
def get_or_create_playlist(sp):
    user_id = sp.current_user()["id"]
    playlists = sp.current_user_playlists(limit=50)["items"]

    for p in playlists:
        if p["name"] == PLAYLIST_NAME:
            return p["id"]

    playlist = sp.user_playlist_create(
        user=user_id,
        name=PLAYLIST_NAME,
        public=False
    )

    return playlist["id"]

# ===== CORE TRACKS =====
def get_core_pools(sp):
    top_tracks = sp.current_user_top_tracks(limit=50)["items"]

    if not top_tracks:
        saved = sp.current_user_saved_tracks(limit=50)["items"]
        top_tracks = [t["track"] for t in saved if t.get("track")]

    if not top_tracks:
        raise Exception("No tracks available")

    core_strong = top_tracks[:20]
    core_medium = top_tracks[20:50] or core_strong

    return core_strong, core_medium

# ===== DISCOVERY =====
def get_near_track(sp, core_strong, core_medium):
    seed = random.choice(core_strong)
    seed_artist_ids = [a["id"] for a in seed["artists"]]
    artist_name = seed["artists"][0]["name"]

    if not artist_name:
        return None

    r = random.random()

    # -------------------------
    # 1. SAME ARTIST (deep cuts)
    # -------------------------
    if r < 0.2:
        results = sp.search(
            q=f"artist:{artist_name}",
            type="track",
            limit=10,
            market="AU"
        )["tracks"]["items"]

        filtered = [
            t for t in results
            if t["id"] != seed["id"]
            and t["id"] not in [x["id"] for x in core_strong + core_medium]
        ]

        if filtered:
            return random.choice(filtered)["uri"]

    # -------------------------
    # 2. ALBUM EXPANSION
    # -------------------------
    elif r < 0.4:
        try:
            album_id = seed["album"]["id"]
            tracks = sp.album_tracks(album_id)["items"]

            filtered = [t for t in tracks if t["id"] != seed["id"]]

            if filtered:
                return random.choice(filtered)["uri"]
        except:
            pass

    # -------------------------
    # 3. PUBLIC PLAYLIST OVERLAP
    # -------------------------
    elif r < 0.6:
        try:
            results = sp.search(
                q=artist_name,
                type="playlist",
                limit=5
            )["playlists"]["items"]

            for playlist in results:

                if not playlist.get("public"):
                    continue

                if playlist["owner"]["id"] != "spotify":
                    continue

                try:
                    tracks = sp.playlist_items(playlist["id"], limit=50)["items"]
                except:
                    continue

                overlap = [
                    t for t in tracks
                    if t["track"]
                    and t["track"]["id"] == seed["id"]
                ]

                if overlap:
                    candidates = [
                        t["track"] for t in tracks
                        if t["track"]
                        and t["track"]["id"] != seed["id"]
                    ]

                    if candidates:
                        return random.choice(candidates)["uri"]

        except:
            pass

    # -------------------------
    # 4. MULTI-SEED BLENDING
    # -------------------------
    elif r < 0.8:
        try:
            seeds = random.sample(core_strong, min(3, len(core_strong)))

            artist_names = [t["artists"][0]["name"] for t in seeds]
            all_seed_ids = [a["id"] for t in seeds for a in t["artists"]]

            query = " ".join(artist_names)

            results = sp.search(
                q=query,
                type="track",
                limit=10,
                market="AU"
            )["tracks"]["items"]

            filtered = [
                t for t in results
                if not any(a["id"] in all_seed_ids for a in t["artists"])
            ]

            if filtered:
                return random.choice(filtered)["uri"]

        except:
            pass

    # -------------------------
    # 5. ARTIST + NEW
    # -------------------------
    else:
        try:
            from datetime import datetime
            current_year = datetime.now().year
            start_year = current_year - random.randint(0, 2)

            results = sp.search(
                q=f"artist:{artist_name} year:{start_year}-{current_year}",
                type="track",
                limit=10,
                market="AU"
            )["tracks"]["items"]

            filtered = [
                t for t in results
                if t["id"] != seed["id"]
            ]

            if filtered:
                return random.choice(filtered)["uri"]

        except:
            pass

    return None

# ===== TRACK SELECTION =====
def get_track(sp, core_strong, core_medium, played_tracks):
    # 70% core, 30% discovery
    if random.random() < 0.7:
        pool = core_strong if random.random() < 0.7 else core_medium

        for _ in range(10):
            track = random.choice(pool)
            if track["uri"] not in played_tracks:
                return track["uri"]

        return random.choice(pool)["uri"]

    else:
        track = get_near_track(sp, core_strong, core_medium)
        if track:
            return track

        return random.choice(core_strong)["uri"]

# ===== PODCAST =====
from datetime import datetime, timedelta

def build_podcast_pool(sp, played_episodes):

    show_queries = [
        "BBC Global News Podcast",
        "The Daily Aus Headlines",
        "FT News Briefing",
        "What the Flux",
        "FT Tech Tonic"
    ]

    candidates = []
    now = datetime.now()
    cutoff = now - timedelta(days=2)

    for query in show_queries:
        try:
            results = sp.search(q=query, type="show", limit=3, market="AU")
            shows = results["shows"]["items"]

            for show in shows:
                episodes = sp.show_episodes(show["id"], limit=20, market="AU")["items"]

                for ep in episodes:
                    if not ep or not ep.get("uri"):
                        continue

                    # DATE
                    release_date = ep.get("release_date")
                    if not release_date:
                        continue

                    try:
                        ep_date = datetime.strptime(release_date, "%Y-%m-%d")
                    except:
                        continue

                    if ep_date < cutoff:
                        continue

                    # LENGTH
                    duration = ep.get("duration_ms", 0)
                    if duration > 35 * 60 * 1000:
                        continue

                    # DAILY AUS STRICT
                    if "daily aus" in query.lower():
                        title = ep["name"].lower()
                        if "headline" not in title and "wrap" not in title:
                            continue

                    if ep["uri"] not in played_episodes:
                        candidates.append(ep["uri"])

        except:
            continue

    print("POOL SIZE:", len(candidates))

    return candidates

# ===== MAIN =====
def run_playlist_builder(sp):
    print("Building playlist...")

    played_tracks = load_memory(TRACK_MEMORY_FILE)
    played_episodes = load_memory(EP_MEMORY_FILE)
    
    podcast_pool = build_podcast_pool(sp, played_episodes)
    random.shuffle(podcast_pool)

    print("PODCAST POOL SIZE:", len(podcast_pool))

    playlist_id = get_or_create_playlist(sp)

    core_strong, core_medium = get_core_pools(sp)

    final_items = []
    block_size = 5
    total_tracks = 25

    songs = []

    for _ in range(total_tracks):
        track = get_track(sp, core_strong, core_medium, played_tracks)
        if track and track not in songs:
            songs.append(track)

    for i in range(0, len(songs), block_size):
        block = songs[i:i+block_size]
        final_items.extend(block)

        if podcast_pool:
            episode_uri = podcast_pool.pop()

            played_episodes.append(episode_uri)
            save_memory(EP_MEMORY_FILE, played_episodes, EP_MEMORY_SIZE)

            final_items.append(episode_uri)

    # save track memory
    played_tracks.extend(songs)
    save_memory(TRACK_MEMORY_FILE, played_tracks, TRACK_MEMORY_SIZE)

    print("Final items:", len(final_items))

    sp.playlist_replace_items(playlist_id, final_items)

    print("Playlist updated")
