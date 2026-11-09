import os
import tempfile
from pathlib import Path

import pytest

from tests.fixture import make_fixture

FIXTURE_DIR = Path(tempfile.mkdtemp(prefix="moviematch_"))
PRIMARY, TASTE = make_fixture(FIXTURE_DIR)
os.environ["MOVIEMATCH_DATA"] = str(FIXTURE_DIR)


@pytest.fixture(scope="session")
def ds():
    from app import data

    return data.load(FIXTURE_DIR)


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
