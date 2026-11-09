import numpy as np
from scipy import sparse

from .config import MIN_COUNT, MIN_SIMILAR

LO, HI = 0.5, 5.0


def _solve_rows(indptr, indices, data, Y, lam, n_rows):
    k = Y.shape[1]
    eye = np.eye(k)
    X = np.zeros((n_rows, k))
    for r in range(n_rows):
        lo, hi = indptr[r], indptr[r + 1]
        if hi == lo:
            continue
        Yi = Y[indices[lo:hi]]
        X[r] = np.linalg.solve(Yi.T @ Yi + lam * (hi - lo) * eye, Yi.T @ data[lo:hi])
    return X


class Recommender:
    """Biased matrix factorisation fitted by ALS; new visitors are folded in by ridge regression."""

    def __init__(self, mu, b, Q, count, lam):
        self.mu, self.b, self.Q, self.count, self.lam = mu, b, Q, count, lam
        self.Qn = Q / (np.linalg.norm(Q, axis=1, keepdims=True) + 1e-9)
        self.eligible = count >= MIN_COUNT
        self.similar_ok = count >= MIN_SIMILAR

    @classmethod
    def fit(cls, matrix, k=32, lam=0.1, lam_item=25.0, iters=12, seed=0):
        R = sparse.csr_matrix(matrix, dtype=np.float64)
        n_users, n_items = R.shape
        mu = float(R.data.mean())
        count = np.diff(R.tocsc().indptr)
        sums = np.asarray(R.sum(0)).ravel()
        b = (sums - mu * count) / (count + lam_item)
        coo = R.tocoo()
        E = sparse.csr_matrix((coo.data - mu - b[coo.col], (coo.row, coo.col)), shape=R.shape)
        Et = E.T.tocsr()
        Q = np.random.default_rng(seed).normal(0, 0.1, (n_items, k))
        for _ in range(iters):
            P = _solve_rows(E.indptr, E.indices, E.data, Q, lam, n_users)
            Q = _solve_rows(Et.indptr, Et.indices, Et.data, P, lam, n_items)
        return cls(mu, b, Q, count, lam)

    def fold_in(self, rated):
        idx = np.fromiter(rated.keys(), dtype=np.int64, count=len(rated))
        y = np.fromiter(rated.values(), dtype=np.float64, count=len(rated)) - self.mu - self.b[idx]
        Yi = self.Q[idx]
        k = Yi.shape[1]
        return np.linalg.solve(Yi.T @ Yi + self.lam * len(idx) * np.eye(k), Yi.T @ y)

    def scores(self, rated):
        return np.clip(self.mu + self.b + self.Q @ self.fold_in(rated), LO, HI)

    def recommend(self, rated, limit=24, allowed=None):
        s = self.scores(rated)
        mask = self.eligible.copy()
        mask[list(rated)] = False
        if allowed is not None:
            mask &= allowed
        order = np.argsort(-np.where(mask, s, -np.inf))[:limit]
        order = order[mask[order]]
        liked = np.array([i for i, r in rated.items() if r >= 4], dtype=np.int64)
        out = []
        for j in order:
            because = []
            if liked.size:
                sims = self.Qn[liked] @ self.Qn[j]
                because = [int(liked[x]) for x in np.argsort(-sims)[:2] if sims[x] > 0]
            out.append((int(j), float(s[j]), because))
        return out

    def similar(self, item, limit=12):
        sims = self.Qn @ self.Qn[item]
        sims[item] = -np.inf
        sims[~self.similar_ok] = -np.inf
        order = np.argsort(-sims)[:limit]
        return [(int(j), float(sims[j])) for j in order if np.isfinite(sims[j])]
