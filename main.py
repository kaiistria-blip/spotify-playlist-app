import spotipy
from spotipy.oauth2 import SpotifyOAuth
import random
from datetime import datetime
import json
import os
   
def run_playlist_builder(sp): 
    print("STEP 1")
    print("Starting...")
    
    print("STEP 2")
    
    # -------- CONSTANTS --------
    TRACK_MEMORY_FILE = "played_tracks.json"
    TRACK_MEMORY_SIZE = 200
    
    PLAYLIST_NAME = "Daily Drive (Auto)"
    
    ARTIST_MEMORY = []
    ARTIST_MEMORY_SIZE = 20
    
    EP_MEMORY_FILE = "played_episodes.json"
    EP_MEMORY_SIZE = 10
    
    # -------- MEMORY FUNCTIONS --------
    def load_track_memory():
        if os.path.exists(TRACK_MEMORY_FILE):
            with open(TRACK_MEMORY_FILE, "r") as f:
                return set(json.load(f))
        return set()
    
    def save_track_memory(memory):
        with open(TRACK_MEMORY_FILE, "w") as f:
            json.dump(list(memory), f)
    
    def load_json(file):
        if os.path.exists(file):
            with open(file, "r") as f:
                return json.load(f)
        return []
    
    def save_json(file, data, limit):
        with open(file, "w") as f:
            json.dump(data[-limit:], f)
    
    played_tracks = load_track_memory()
    played_episodes = load_json(EP_MEMORY_FILE)
    
    # -------- PLAYLIST GET/CREATE --------
    def get_or_create_playlist():
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
    
    # -------- SONG SYSTEM --------
    top_tracks = sp.current_user_top_tracks(limit=50, time_range="short_term").get("items", [])
    
    if not top_tracks:
        print("WARNING: No top tracks, using saved tracks")
        saved = sp.current_user_saved_tracks(limit=50).get("items", [])
        top_tracks = [t["track"] for t in saved if t.get("track")]
    
    if not top_tracks:
        print("WARNING: No saved tracks, using search fallback")
        results = sp.search(q="genre:pop", type="track", limit=50, market="AU")
        top_tracks = results["tracks"]["items"]
    
    if not top_tracks:
        raise Exception("No tracks available from any source")
    
    print("STEP 3")
    print("TOP TRACKS LENGTH:", len(top_tracks))
    
    core_strong = top_tracks[0:20]     # Top 1–20
    
    if not core_strong:
        raise Exception("FATAL: core_strong is empty")
    
    core_medium = top_tracks[20:50]   # Top 21–50
    
    if not core_medium:
        core_medium = core_strong
    
    current_year = datetime.now().year
    start_year = current_year - random.randint(0, 2)
    
    
    def get_artist_ids(track):
        return [a["id"] for a in track["artists"]]
    
    def is_valid_new_track(track, seed_artist_ids):
        track_artist_ids = [a["id"] for a in track["artists"]]
    
        return (
            not any(a in seed_artist_ids for a in track_artist_ids)
            or len(track_artist_ids) > 1
        )
    
    def get_core_track():
        # 70% strong favourites
        if random.random() < 0.7:
            pool = core_strong
        else:
            pool = core_medium
    
        for _ in range(10):  # try multiple times
            if random.random() < 0.7:
                track = random.choice(core_strong)
            else:
                track = random.choice(core_medium)
    
            if track["uri"] not in played_tracks:
                return track["uri"]
    
        # fallback if everything has been played
        return random.choice(core_strong)["uri"]
    
    def get_near_track():
        seed = random.choice(core_strong)
        seed_artist_ids = get_artist_ids(seed)
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
    
            # remove songs already in top/core
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
    
                    # skip private / inaccessible playlists
                    if not playlist.get("public"):
                        continue
    
                    # prioritise higher quality playlists (optional but recommended)
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
        elif r < 0.8:
            try:
                seeds = random.sample(core_strong, min(3, len(core_strong)))
    
                artist_names = [t["artists"][0]["name"] for t in seeds]
                all_seed_ids = [a for t in seeds for a in get_artist_ids(t)]
    
                query = " ".join(artist_names)
    
                results = sp.search(
                    q=query,
                    type="track",
                    limit=10,
                    market="AU"
                )["tracks"]["items"]
    
                filtered = [
                    t for t in results
                    if is_valid_new_track(t, all_seed_ids)
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
    
            except Exception as e:
                print(f"Near discovery failed: {e}")
    
        return None
    
    # -------- PODCAST FUNCTION --------
    
    def get_podcast():
        global played_episodes
    
        show_queries = [
            "BBC Global News Podcast",
            "The Daily Aus Headlines",
            "FT News Briefing",
            "What the Flux",
            "FT Tech Tonic"
        ]
    
        random.shuffle(show_queries)
    
        for query in show_queries:
            try:
                results = sp.search(q=query, type="show", limit=3, market="AU")
                shows = results["shows"]["items"]
    
                for show in shows:
                    episodes = sp.show_episodes(show["id"], limit=5, market="AU")["items"]
    
                    for ep in episodes:
    
                        if ep["uri"] in played_episodes:
                            continue
    
                        if "daily aus" in query.lower():
                            title = ep["name"].lower()
                            if "headline" not in title and "wrap" not in title:
                                continue
    
                        played_episodes.append(ep["uri"])
                        save_json(EP_MEMORY_FILE, played_episodes, EP_MEMORY_SIZE)
    
                        return ep["uri"]
    
            except:
                continue
    
        # fallback (always return something)
        try:
            results = sp.search(q="news podcast", type="show", limit=1, market="AU")
            show = results["shows"]["items"][0]
            ep = sp.show_episodes(show["id"], limit=1, market="AU")["items"][0]
            return ep["uri"]
        except:
            return None
    
    # -------- 5 BLOCK SYSTEM --------
    TOTAL_BLOCKS = 5
    SONGS_PER_BLOCK = 5
    
    all_items = []
    
    for block in range(TOTAL_BLOCKS):
    
        block_songs = []
        attempts = 0
    
        # STRICT PHASE 
        while len(block_songs) < SONGS_PER_BLOCK and attempts < 50:
            attempts += 1
    
            r = random.random()
    
            if r < 0.6:
                track = get_core_track()
            else:
                try:
                    print("CALLING get_near_track")
                    track = get_near_track()
                    print("RETURNED get_near_track")
                except Exception as e:
                    print("ERROR in get_near_track:", e)
                    track = None
    
                if not track:
                    track = get_core_track()
    
            if isinstance(track, str) and track not in block_songs:
                block_songs.append(track)
    
        # RELAXED PHASE
        while len(block_songs) < SONGS_PER_BLOCK:
            track = get_core_track()
            if track and track not in block_songs:
                block_songs.append(track)
    
        random.shuffle(block_songs)
        all_items.extend(block_songs)
    
        print("SANITISING all_items...")
    
        clean_all_items = [
            i for i in all_items
            if isinstance(i, str) and i.startswith("spotify:")
        ]
    
        print("VALID ITEMS:", len(clean_all_items))
    
        all_items = clean_all_items
    
        # ADD PODCAST
        try:
            print("CALLING get_podcast")
            episode_uri = get_podcast()
            print("RETURNED get_podcast")
        except Exception as e:
            print("ERROR in get_podcast:", e)
            episode_uri = None    
        
        if episode_uri:
            all_items.append(episode_uri)
    
    # -------- SAVE TRACK MEMORY --------
    try:
        clean_tracks = [
            i for i in all_items
            if isinstance(i, str) and i.startswith("spotify:track")
        ]
    
        print("CLEAN TRACK COUNT:", len(clean_tracks))
    
        played_tracks.update(clean_tracks)
    
        # trim BEFORE saving
        played_tracks = set(list(played_tracks)[-200:])
    
        save_track_memory(played_tracks)
    
        print("SAVING TRACK MEMORY...")
    
        save_track_memory(played_tracks)
    
        print("TRACK MEMORY SAVED")
    
    except Exception as e:
        print("ERROR saving track memory:", e)
    # -------- UPDATE PLAYLIST --------
    
    print("STEP 4 - getting playlist")
    
    try:
        playlist_id = get_or_create_playlist()
        print("STEP 5 - got playlist:", playlist_id)
    except Exception as e:
        print("FAILED at get_or_create_playlist:", e)
        raise
    
    print("STEP 6 - replacing items")
    
    try:
        sp.playlist_replace_items(playlist_id, all_items)
        print("STEP 7 - replaced items")
    except Exception as e:
        print("FAILED at playlist_replace_items:", e)
        raise
    
    print("Done")
