"""Movie poster lookup via the TMDB API, cached on disk.

Set TMDB_API_KEY (v3 key or v4 read-access token) to enable. Without it the site shows generated tiles.
"""
import json
import os
import threading
import urllib.error
import urllib.request

from .config import DATA

API = os.environ.get("TMDB_API_URL", "https://api.themoviedb.org/3")
IMAGE = os.environ.get("TMDB_IMAGE_URL", "https://image.tmdb.org/t/p/w342")
CACHE = DATA / "posters.json"
SAVE_EVERY = 25


class Transient(Exception):
    """Network or rate-limit problem; do not cache."""


def api_key():
    return os.environ.get("TMDB_API_KEY", "").strip()


def enabled():
    return bool(api_key())


def _fetch_path(tmdb_id):
    key = api_key()
    url = f"{API}/movie/{tmdb_id}"
    headers = {"Accept": "application/json"}
    if len(key) > 40:
        headers["Authorization"] = f"Bearer {key}"
    else:
        url += f"?api_key={key}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10) as r:
            return json.load(r).get("poster_path") or ""
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return ""
        raise Transient(str(e)) from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise Transient(str(e)) from e


class Posters:
    def __init__(self, tmdb_ids):
        self.tmdb = tmdb_ids
        self.lock = threading.Lock()
        self.dirty = 0
        try:
            self.cache = json.loads(CACHE.read_text())
        except (OSError, ValueError):
            self.cache = {}

    @property
    def available(self):
        return enabled() and bool(self.tmdb)

    def url(self, movie_id):
        """Poster URL, or None if unknown. Raises Transient on temporary failure."""
        key = str(movie_id)
        if key in self.cache:
            return IMAGE + self.cache[key] if self.cache[key] else None
        tmdb_id = self.tmdb.get(movie_id)
        if not enabled() or tmdb_id is None:
            return None
        path = _fetch_path(tmdb_id)
        with self.lock:
            self.cache[key] = path
            self.dirty += 1
            if self.dirty >= SAVE_EVERY:
                self.save()
        return IMAGE + path if path else None

    def save(self):
        try:
            CACHE.write_text(json.dumps(self.cache))
            self.dirty = 0
        except OSError:
            pass
