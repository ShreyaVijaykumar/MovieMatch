import numpy as np

from app import evaluate
from app.model import Recommender
from tests.conftest import PRIMARY
from tests.fixture import GENRES


def _items_of(genre, ds, n=6):
    return [i for i in range(ds.n_items - 1) if GENRES[PRIMARY[i]] == genre and ds.count[i] >= 10][:n]


def test_recommendations_follow_taste(ds):
    model = Recommender.fit(ds.matrix())
    rated = {i: 5.0 for i in _items_of("Sci-Fi", ds)}
    recs = model.recommend(rated, 10)
    share = np.mean([GENRES[PRIMARY[j]] == "Sci-Fi" for j, _, _ in recs])
    assert share >= 0.8


def test_excludes_rated_and_rare_items(ds):
    model = Recommender.fit(ds.matrix())
    rated = {i: 5.0 for i in _items_of("Drama", ds)}
    recs = model.recommend(rated, 50)
    ids = [j for j, _, _ in recs]
    assert not set(ids) & set(rated)
    assert all(ds.count[j] >= 10 for j in ids)
    assert all(0.5 <= s <= 5 for _, s, _ in recs)


def test_similar_items_share_genre(ds):
    model = Recommender.fit(ds.matrix())
    anchor = _items_of("Horror", ds, 1)[0]
    sims = model.similar(anchor, 8)
    assert anchor not in [j for j, _ in sims]
    assert np.mean([GENRES[PRIMARY[j]] == "Horror" for j, _ in sims]) >= 0.6


def test_split_is_temporal_and_disjoint(ds):
    train, test = evaluate.temporal_split(ds)
    assert not (train & test).any()
    for u in range(0, ds.n_users, 17):
        tr, te = ds.times[train & (ds.users == u)], ds.times[test & (ds.users == u)]
        if len(tr) and len(te):
            assert tr.max() <= te.min()


def test_model_beats_baselines(ds):
    res = evaluate.run(ds, n_users=100)
    assert res["rmse"]["matrix factorisation"] < res["rmse"]["global mean"]
    assert res["rmse"]["matrix factorisation"] < res["rmse"]["item average"]
