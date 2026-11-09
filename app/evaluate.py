import json

import numpy as np

from . import data
from .config import DATA, METRICS, MIN_COUNT
from .model import Recommender

TOP = 10
LIKED = 4.0


def temporal_split(ds, frac=0.2, min_ratings=10):
    order = np.lexsort((ds.times, ds.users))
    n_per = np.bincount(ds.users, minlength=ds.n_users)
    start = np.concatenate([[0], np.cumsum(n_per)[:-1]])
    pos = np.empty(len(order), dtype=np.int64)
    pos[order] = np.arange(len(order)) - np.repeat(start, n_per)
    cut = np.floor(n_per * (1 - frac)).astype(np.int64)
    test = (pos >= cut[ds.users]) & (n_per[ds.users] >= min_ratings)
    return ~test, test


def _ndcg(hits):
    gains = sum(1 / np.log2(i + 2) for i, h in enumerate(hits) if h)
    return gains


def run(ds, n_users=400, seed=0):
    train, test = temporal_split(ds)
    model = Recommender.fit(ds.matrix(train))
    rng = np.random.default_rng(seed)
    users = np.unique(ds.users[test])
    users = rng.choice(users, size=min(n_users, len(users)), replace=False)

    err = {"global mean": [], "item average": [], "matrix factorisation": []}
    rank = {m: {"hit": [], "ndcg": [], "recall": []} for m in ("popularity", "item average", "matrix factorisation")}
    n_test = 0
    for u in users:
        tr = train & (ds.users == u)
        te = test & (ds.users == u)
        rated = dict(zip(ds.items[tr].tolist(), ds.values[tr].tolist()))
        if not rated:
            continue
        s_mf = model.scores(rated)
        t_items, t_vals = ds.items[te], ds.values[te]
        n_test += len(t_items)
        err["global mean"] += ((t_vals - model.mu) ** 2).tolist()
        err["item average"] += ((t_vals - np.clip(model.mu + model.b[t_items], 0.5, 5)) ** 2).tolist()
        err["matrix factorisation"] += ((t_vals - s_mf[t_items]) ** 2).tolist()

        relevant = set(t_items[t_vals >= LIKED].tolist())
        if not relevant:
            continue
        cand = model.eligible.copy()
        cand[list(rated)] = False
        score_sets = {
            "popularity": model.count.astype(float),
            "item average": model.mu + model.b,
            "matrix factorisation": s_mf,
        }
        for name, s in score_sets.items():
            top = np.argsort(-np.where(cand, s, -np.inf))[:TOP]
            hits = [int(j) in relevant for j in top]
            rank[name]["hit"].append(float(any(hits)))
            rank[name]["recall"].append(sum(hits) / len(relevant))
            ideal = _ndcg([True] * min(len(relevant), TOP))
            rank[name]["ndcg"].append(_ndcg(hits) / ideal)

    return {
        "split": "last 20% of each user's ratings by time (users with 10+ ratings)",
        "users_evaluated": len(users),
        "test_ratings": n_test,
        "users_ranked": len(rank["popularity"]["hit"]),
        "rmse": {k: round(float(np.sqrt(np.mean(v))), 4) for k, v in err.items()},
        "ranking": {
            k: {
                f"hit@{TOP}": round(float(np.mean(v["hit"])), 4),
                f"recall@{TOP}": round(float(np.mean(v["recall"])), 4),
                f"ndcg@{TOP}": round(float(np.mean(v["ndcg"])), 4),
            }
            for k, v in rank.items()
        },
        "relevant_rating": f">= {LIKED}",
        "min_ratings_to_rank": MIN_COUNT,
    }


def main():
    result = run(data.load(DATA))
    METRICS.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
