import pytest

from app.data import parse_title


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Toy Story (1995)", ("Toy Story", 1995)),
        ("Matrix, The (1999)", ("The Matrix", 1999)),
        ("American President, The (1995)", ("The American President", 1995)),
        ("Unknown Film", ("Unknown Film", None)),
        ("City of Lost Children, The (Cité des enfants perdus, La) (1995)", ("City of Lost Children, The (Cité des enfants perdus, La)", 1995)),
    ],
)
def test_parse_title(raw, expected):
    assert parse_title(raw) == expected


def test_loader_shapes(ds):
    assert ds.n_items == 301 and ds.n_users == 120
    assert len(ds.values) == len(ds.users) == len(ds.items) == len(ds.times) == 9000
    assert ds.count.sum() == 9000
    assert ds.matrix().shape == (120, 301)
    assert ds.genres[-1] == []
    assert ds.values.min() >= 0.5 and ds.values.max() <= 5


def test_missing_data_message(tmp_path):
    from app import data

    with pytest.raises(FileNotFoundError, match="fetch_data"):
        data.load(tmp_path)
