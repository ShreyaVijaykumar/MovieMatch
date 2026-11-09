"""Pre-fetch poster paths from TMDB into data/ml-latest-small/posters.json.

Usage: TMDB_API_KEY=... python scripts/fetch_posters.py [--min-ratings 5]
Optional: the server also fetches posters on demand.
"""
import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import data, posters  # noqa: E402
from app.config import DATA  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-ratings", type=int, default=5)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if not posters.enabled():
        sys.exit("Set TMDB_API_KEY first (free key: https://www.themoviedb.org/settings/api)")

    ds = data.load(DATA)
    store = posters.Posters(ds.tmdb)
    todo = [int(ds.movie_ids[i]) for i in range(ds.n_items) if ds.count[i] >= args.min_ratings and int(ds.movie_ids[i]) in ds.tmdb]
    todo = [m for m in todo if str(m) not in store.cache]
    print(f"{len(todo):,} posters to fetch")
    done = found = failed = 0

    def work(movie_id):
        try:
            return store.url(movie_id) is not None
        except posters.Transient:
            return None

    with ThreadPoolExecutor(args.workers) as ex:
        for r in ex.map(work, todo):
            done += 1
            found += r is True
            failed += r is None
            if done % 250 == 0:
                print(f"{done:,}/{len(todo):,}")
    store.save()
    print(f"done: {found:,} posters, {done - found - failed:,} without poster, {failed:,} failed (rerun to retry)")


if __name__ == "__main__":
    main()
