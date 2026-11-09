"""Smoke-check a running server. Usage: python scripts/check.py [base_url]"""
import json
import sys
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
failed = []


def call(path, body=None):
    req = urllib.request.Request(
        BASE + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r) if "json" in r.headers.get("Content-Type", "") else r.read().decode()


def step(name, fn):
    try:
        detail = fn()
        print(f"PASS  {name}" + (f"  ({detail})" if detail else ""))
    except Exception as e:
        failed.append(name)
        print(f"FAIL  {name}  ({e})")


ctx = {}


def t_health():
    assert call("/health") == {"status": "ok"}


def t_page():
    assert "MovieMatch" in call("/")


def t_meta():
    m = call("/api/meta")
    assert m["movies"] > 0 and m["ratings"] > 0
    return f'{m["movies"]:,} movies, {m["ratings"]:,} ratings'


def t_movies():
    r = call("/api/movies?limit=5")
    assert len(r["items"]) == 5
    return r["items"][0]["title"]


def t_onboarding():
    ctx["items"] = call("/api/onboarding?n=6")
    assert len(ctx["items"]) >= 5


def t_recommend():
    ratings = {str(m["id"]): 5 for m in ctx["items"][:5]}
    r = call("/api/recommend", {"ratings": ratings, "limit": 5})
    assert len(r["items"]) > 0
    return r["items"][0]["title"]


for name, fn in [("health", t_health), ("home page", t_page), ("dataset loaded", t_meta), ("movie list", t_movies),
                 ("onboarding", t_onboarding), ("recommendations", t_recommend)]:
    step(name, fn)

print("\nAll checks passed" if not failed else f"\n{len(failed)} failed: {', '.join(failed)}")
sys.exit(1 if failed else 0)
