import json
from collections import Counter
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import data
from .config import DATA, METRICS, MIN_COUNT, STATIC
from . import posters as tmdb
from .model import Recommender

PRIOR_WEIGHT = 20
ONBOARD_PER_GENRE = 3


class _State:
    pass


def _prepare(ds, model):
    s = _State()
    s.ds, s.model = ds, model
    rated = ds.count > 0
    c_mean = float(ds.mean[rated].mean())
    s.weighted = (ds.count / (ds.count + PRIOR_WEIGHT)) * ds.mean + (PRIOR_WEIGHT / (ds.count + PRIOR_WEIGHT)) * c_mean
    s.lower = [t.casefold() for t in ds.titles]
    s.genre_freq = Counter(g for gs in ds.genres for g in gs)
    s.genre_masks = {g: np.array([g in gs for gs in ds.genres]) for g in s.genre_freq}
    order = np.argsort(-ds.count)
    chosen, used = [], Counter()
    for i in order[:400]:
        if not ds.genres[i] or any(used[g] >= ONBOARD_PER_GENRE for g in ds.genres[i][:1]):
            continue
        chosen.append(int(i))
        used[ds.genres[i][0]] += 1
        if len(chosen) >= 30:
            break
    s.onboarding = chosen
    return s


@asynccontextmanager
async def lifespan(app):
    ds = data.load(DATA)
    app.state.s = _prepare(ds, Recommender.fit(ds.matrix()))
    app.state.posters = tmdb.Posters(ds.tmdb)
    yield
    app.state.posters.save()


app = FastAPI(title="MovieMatch", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


def _movie(s, i):
    ds = s.ds
    return {
        "id": int(ds.movie_ids[i]),
        "title": ds.titles[i],
        "year": ds.years[i],
        "genres": ds.genres[i],
        "avg": round(float(ds.mean[i]), 2),
        "count": int(ds.count[i]),
    }


class RecommendIn(BaseModel):
    ratings: dict[str, float]
    limit: int = Field(24, ge=1, le=60)
    genre: str | None = None


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta(request: Request):
    s = request.app.state.s
    return {
        "movies": s.ds.n_items,
        "ratings": int(len(s.ds.values)),
        "users": s.ds.n_users,
        "genres": [g for g, _ in s.genre_freq.most_common()],
        "posters": request.app.state.posters.available,
    }


@app.get("/api/poster/{movie_id}")
def poster(request: Request, movie_id: int):
    try:
        url = request.app.state.posters.url(movie_id)
    except tmdb.Transient:
        return Response(status_code=404, headers={"Cache-Control": "no-store"})
    if not url:
        return Response(status_code=404, headers={"Cache-Control": "public, max-age=3600"})
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/metrics")
def metrics():
    return json.loads(METRICS.read_text()) if METRICS.exists() else {}


@app.get("/api/movies")
def movies(
    request: Request,
    q: str = "",
    genre: str | None = None,
    sort: str = Query("popular", pattern="^(popular|rating|year|title)$"),
    limit: int = Query(24, ge=1, le=60),
    offset: int = Query(0, ge=0),
):
    s = request.app.state.s
    ds = s.ds
    keep = np.ones(ds.n_items, dtype=bool)
    if genre:
        if genre not in s.genre_masks:
            raise HTTPException(404, f"unknown genre: {genre}")
        keep &= s.genre_masks[genre]
    if q:
        needle = q.casefold()
        keep &= np.array([needle in t for t in s.lower])
    if sort in ("popular", "rating"):
        keep &= ds.count >= (1 if sort == "popular" else MIN_COUNT)
    idx = np.flatnonzero(keep)
    if sort == "popular":
        idx = idx[np.argsort(-ds.count[idx], kind="stable")]
    elif sort == "rating":
        idx = idx[np.argsort(-s.weighted[idx], kind="stable")]
    elif sort == "year":
        idx = idx[np.argsort([-(ds.years[i] or 0) for i in idx], kind="stable")]
    else:
        idx = idx[np.argsort([s.lower[i] for i in idx], kind="stable")]
    return {"total": int(len(idx)), "items": [_movie(s, i) for i in idx[offset : offset + limit]]}


@app.get("/api/movies/{movie_id}")
def movie_detail(request: Request, movie_id: int):
    s = request.app.state.s
    i = s.ds.index.get(movie_id)
    if i is None:
        raise HTTPException(404, "unknown movie")
    similar = [{**_movie(s, j), "similarity": round(sim, 3)} for j, sim in s.model.similar(i)]
    return {**_movie(s, i), "similar": similar}


@app.get("/api/onboarding")
def onboarding(request: Request, n: int = Query(24, ge=1, le=30)):
    s = request.app.state.s
    return [_movie(s, i) for i in s.onboarding[:n]]


@app.post("/api/recommend")
def recommend(request: Request, body: RecommendIn):
    s = request.app.state.s
    rated = {}
    for key, value in body.ratings.items():
        try:
            i = s.ds.index.get(int(key))
        except ValueError:
            i = None
        if i is not None and 0.5 <= value <= 5:
            rated[i] = float(value)
    if not rated:
        raise HTTPException(422, "no valid ratings")
    allowed = None
    if body.genre:
        if body.genre not in s.genre_masks:
            raise HTTPException(404, f"unknown genre: {body.genre}")
        allowed = s.genre_masks[body.genre]
    items = []
    for j, score, because in s.model.recommend(rated, body.limit, allowed):
        items.append(
            {
                **_movie(s, j),
                "score": round(score, 2),
                "match": int(round((score - 0.5) / 4.5 * 100)),
                "because": [s.ds.titles[b] for b in because],
            }
        )
    return {"n_ratings": len(rated), "items": items}
