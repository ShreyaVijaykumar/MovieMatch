from tests.conftest import PRIMARY
from tests.fixture import GENRES


def test_pages_and_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert "MovieMatch" in client.get("/").text
    assert client.get("/static/app.js").status_code == 200


def test_meta(client):
    m = client.get("/api/meta").json()
    assert m["movies"] == 301 and m["ratings"] == 9000 and m["users"] == 120
    assert set(GENRES) <= set(m["genres"])


def test_movies_search_filter_sort_paging(client):
    r = client.get("/api/movies?q=film 1&limit=5").json()
    assert r["total"] > 5 and len(r["items"]) == 5
    assert all("film 1" in x["title"].lower() for x in r["items"])
    counts = [x["count"] for x in client.get("/api/movies?sort=popular&limit=20").json()["items"]]
    assert counts == sorted(counts, reverse=True)
    horror = client.get("/api/movies?genre=Horror&limit=60").json()["items"]
    assert horror and all("Horror" in x["genres"] for x in horror)
    p1 = client.get("/api/movies?limit=10&offset=0").json()["items"]
    p2 = client.get("/api/movies?limit=10&offset=10").json()["items"]
    assert not {x["id"] for x in p1} & {x["id"] for x in p2}
    assert client.get("/api/movies?genre=Nope").status_code == 404
    assert client.get("/api/movies?sort=bad").status_code == 422
    assert client.get("/api/movies?sort=year&limit=3").json()["items"][0]["year"] >= 2000


def test_title_article_and_missing_genre(client):
    titles = [x["title"] for x in client.get("/api/movies?q=synthetic film 25&limit=60").json()["items"]]
    assert "The Synthetic Film 25" in titles
    nog = client.get("/api/movies?q=no genre&sort=title").json()["items"]
    assert nog and nog[0]["genres"] == []


def test_detail(client):
    top = client.get("/api/movies?limit=1").json()["items"][0]
    d = client.get(f"/api/movies/{top['id']}").json()
    assert d["id"] == top["id"] and 1 <= len(d["similar"]) <= 12
    assert top["id"] not in [s["id"] for s in d["similar"]]
    assert client.get("/api/movies/999999").status_code == 404


def test_onboarding(client):
    items = client.get("/api/onboarding?n=24").json()
    assert 10 <= len(items) <= 24
    assert len({x["id"] for x in items}) == len(items)


def test_recommend(client):
    ids = [i + 1 for i in range(300) if GENRES[PRIMARY[i]] == "Romance"][:6]
    ratings = {str(i): 5 for i in ids}
    r = client.post("/api/recommend", json={"ratings": ratings, "limit": 10}).json()
    assert r["n_ratings"] == 6 and 0 < len(r["items"]) <= 10
    assert not {x["id"] for x in r["items"]} & set(ids)
    assert all(0 <= x["match"] <= 100 for x in r["items"])
    assert any(x["because"] for x in r["items"])
    g = client.post("/api/recommend", json={"ratings": ratings, "genre": "Horror"}).json()["items"]
    assert all("Horror" in x["genres"] for x in g)


def test_recommend_validation(client):
    assert client.post("/api/recommend", json={"ratings": {}}).status_code == 422
    assert client.post("/api/recommend", json={"ratings": {"abc": 5, "999999": 4, "1": 9}}).status_code == 422
    assert client.post("/api/recommend", json={"ratings": {"1": 5}, "limit": 999}).status_code == 422
    assert client.post("/api/recommend", json={"ratings": {"1": 5}, "genre": "Nope"}).status_code == 404
