"""Synthetic data in MovieLens file format, with planted genre taste. For tests only."""
import csv
from pathlib import Path

import numpy as np

GENRES = ["Action", "Comedy", "Drama", "Sci-Fi", "Romance", "Horror"]


def make_fixture(path, n_users=120, n_movies=300, n_ratings=9000, seed=0):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    primary = rng.integers(len(GENRES), size=n_movies)
    popularity = rng.pareto(1.2, n_movies) + 1
    popularity /= popularity.sum()
    rows = []
    for m in range(n_movies):
        g = [GENRES[primary[m]]]
        if rng.random() < 0.3:
            g.append(GENRES[(primary[m] + 1) % len(GENRES)])
        title = f"Synthetic Film {m}"
        if m % 25 == 0:
            title = f"Synthetic Film {m}, The"
        if m % 40 == 1:
            title = f"Comma, Colon: Film {m}"
        rows.append((m + 1, f"{title} ({1960 + m % 60})", "|".join(g)))
    rows.append((n_movies + 1, "No Genre Film (2001)", "(no genres listed)"))
    with open(path / "movies.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["movieId", "title", "genres"])
        w.writerows(rows)

    with open(path / "links.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["movieId", "imdbId", "tmdbId"])
        for m in range(1, n_movies + 1):
            w.writerow([m, f"{m:07d}", 1000 + m if m % 10 else ""])

    taste = [rng.choice(len(GENRES), size=2, replace=False) for _ in range(n_users)]
    seen, out = set(), []
    t0 = 1_000_000_000
    while len(out) < n_ratings:
        u = int(rng.integers(n_users))
        m = int(rng.choice(n_movies, p=popularity))
        if (u, m) in seen:
            continue
        seen.add((u, m))
        liked = primary[m] in taste[u]
        r = 3.0 + (1.3 if liked else -0.7) + rng.normal(0, 0.6)
        r = float(np.clip(np.round(r * 2) / 2, 0.5, 5.0))
        out.append((u + 1, m + 1, r, t0 + len(out) * 1000 + int(rng.integers(500))))
    with open(path / "ratings.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["userId", "movieId", "rating", "timestamp"])
        w.writerows(out)
    return primary, taste
