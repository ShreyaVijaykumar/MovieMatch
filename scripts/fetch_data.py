"""Download MovieLens ml-latest-small (GroupLens) into data/ml-latest-small."""
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
OUT = Path(__file__).resolve().parent.parent / "data"
FILES = ("movies.csv", "ratings.csv", "links.csv", "tags.csv", "README.txt")


def main():
    target = OUT / "ml-latest-small"
    target.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {URL}")
    with urllib.request.urlopen(URL, timeout=60) as r:
        blob = r.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for name in z.namelist():
            base = name.rsplit("/", 1)[-1]
            if base in FILES:
                (target / base).write_bytes(z.read(name))
    for f in ("movies.csv", "ratings.csv"):
        n = sum(1 for _ in open(target / f, encoding="utf-8")) - 1
        print(f"{f}: {n:,} rows")
    print(f"Saved to {target}")


if __name__ == "__main__":
    sys.exit(main())
