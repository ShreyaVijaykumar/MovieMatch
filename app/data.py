import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy import sparse

YEAR = re.compile(r"\s*\((\d{4})\)\s*$")
ARTICLE = re.compile(r"^(.*), (The|A|An)$")


def parse_title(raw):
    m = YEAR.search(raw)
    year = int(m.group(1)) if m else None
    title = raw[: m.start()] if m else raw
    a = ARTICLE.match(title)
    if a:
        title = f"{a.group(2)} {a.group(1)}"
    return title.strip(), year


@dataclass
class Dataset:
    movie_ids: np.ndarray
    titles: list
    years: list
    genres: list
    users: np.ndarray
    items: np.ndarray
    values: np.ndarray
    times: np.ndarray
    n_users: int
    count: np.ndarray
    mean: np.ndarray
    index: dict
    tmdb: dict = field(default_factory=dict)

    @property
    def n_items(self):
        return len(self.titles)

    def matrix(self, sel=None):
        sel = slice(None) if sel is None else sel
        return sparse.csr_matrix(
            (self.values[sel], (self.users[sel], self.items[sel])), shape=(self.n_users, self.n_items)
        )


def load(path):
    path = Path(path)
    movies, ratings = path / "movies.csv", path / "ratings.csv"
    if not movies.exists() or not ratings.exists():
        raise FileNotFoundError(f"MovieLens data not found in {path}. Run: python scripts/fetch_data.py")
    with open(movies, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    ids = np.array([int(r["movieId"]) for r in rows])
    index = {int(m): i for i, m in enumerate(ids)}
    parsed = [parse_title(r["title"]) for r in rows]
    genres = [[] if r["genres"] in ("", "(no genres listed)") else r["genres"].split("|") for r in rows]

    raw = np.loadtxt(ratings, delimiter=",", skiprows=1, usecols=(0, 1, 2, 3), ndmin=2)
    items = np.array([index.get(int(m), -1) for m in raw[:, 1]])
    keep = items >= 0
    raw, items = raw[keep], items[keep]
    _, users = np.unique(raw[:, 0].astype(np.int64), return_inverse=True)
    n_items = len(rows)
    count = np.bincount(items, minlength=n_items)
    sums = np.bincount(items, weights=raw[:, 2], minlength=n_items)
    tmdb = {}
    links = path / "links.csv"
    if links.exists():
        with open(links, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("tmdbId", "").strip().isdigit():
                    tmdb[int(r["movieId"])] = int(r["tmdbId"])
    return Dataset(
        movie_ids=ids,
        titles=[p[0] for p in parsed],
        years=[p[1] for p in parsed],
        genres=genres,
        users=users.astype(np.int64),
        items=items.astype(np.int64),
        values=raw[:, 2].astype(np.float64),
        times=raw[:, 3].astype(np.int64),
        n_users=int(users.max()) + 1,
        count=count,
        mean=np.divide(sums, count, out=np.zeros(n_items), where=count > 0),
        index=index,
        tmdb=tmdb,
    )
