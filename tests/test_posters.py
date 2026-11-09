import pytest

from app import posters


@pytest.fixture
def tmdb_on(monkeypatch, client):
    monkeypatch.setenv("TMDB_API_KEY", "test-key")
    calls = []

    def fake(tmdb_id):
        calls.append(tmdb_id)
        if tmdb_id == 1003:
            return ""
        if tmdb_id == 1004:
            raise posters.Transient("boom")
        return f"/p{tmdb_id}.jpg"

    monkeypatch.setattr(posters, "_fetch_path", fake)
    client.app.state.posters.cache.clear()
    return calls


def test_disabled_without_key(client, monkeypatch):
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    assert client.get("/api/meta").json()["posters"] is False
    assert client.get("/api/poster/1", follow_redirects=False).status_code == 404


def test_redirects_to_tmdb_and_caches(client, tmdb_on):
    assert client.get("/api/meta").json()["posters"] is True
    r = client.get("/api/poster/1", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == posters.IMAGE + "/p1001.jpg"
    assert "max-age" in r.headers["cache-control"]
    client.get("/api/poster/1", follow_redirects=False)
    assert tmdb_on.count(1001) == 1


def test_missing_poster_cached_as_404(client, tmdb_on):
    assert client.get("/api/poster/3", follow_redirects=False).status_code == 404
    client.get("/api/poster/3", follow_redirects=False)
    assert tmdb_on.count(1003) == 1


def test_transient_error_not_cached(client, tmdb_on):
    r = client.get("/api/poster/4", follow_redirects=False)
    assert r.status_code == 404 and r.headers["cache-control"] == "no-store"
    client.get("/api/poster/4", follow_redirects=False)
    assert tmdb_on.count(1004) == 2


def test_movie_without_tmdb_id(client, tmdb_on):
    assert client.get("/api/poster/10", follow_redirects=False).status_code == 404
    assert tmdb_on == []


def test_links_loaded(ds):
    assert ds.tmdb[1] == 1001 and 10 not in ds.tmdb


def test_bearer_token_header(monkeypatch):
    seen = {}

    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"poster_path": "/z.jpg"}'

    def fake_urlopen(req, timeout):
        seen.update(req.headers)
        seen["url"] = req.full_url
        return R()

    monkeypatch.setenv("TMDB_API_KEY", "x" * 60)
    monkeypatch.setattr(posters.urllib.request, "urlopen", fake_urlopen)
    assert posters._fetch_path(5) == "/z.jpg"
    assert seen["Authorization"].startswith("Bearer ") and "api_key" not in seen["url"]


def test_dotenv_loader(tmp_path, monkeypatch):
    from app.config import _load_env

    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.delenv("OTHER_VAR", raising=False)
    (tmp_path / ".env").write_text('# comment\nTMDB_API_KEY = "abc123"\nOTHER_VAR=\n', encoding="utf-8")
    _load_env(tmp_path / ".env")
    import os

    assert os.environ["TMDB_API_KEY"] == "abc123" and "OTHER_VAR" not in os.environ
    monkeypatch.setenv("TMDB_API_KEY", "from-shell")
    _load_env(tmp_path / ".env")
    assert os.environ["TMDB_API_KEY"] == "from-shell"
    monkeypatch.delenv("TMDB_API_KEY")
