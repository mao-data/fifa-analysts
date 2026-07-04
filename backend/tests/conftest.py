import pytest

from app.db import get_conn
from app.etl.base import MatchRow, replace_source


@pytest.fixture
def conn(tmp_path):
    c = get_conn(tmp_path / "test.db")
    yield c
    c.close()


def make_match(home, away, hs, as_, date="2024-01-01", group="en.1", season="2023-24",
               competition="Premier League", neutral=False, scope="league",
               source="test"):
    return MatchRow(source=source, scope=scope, rating_group=group,
                    competition=competition, season=season, date=date,
                    home_team=home, away_team=away, home_score=hs, away_score=as_,
                    neutral=neutral)


def load(conn, rows, source="test"):
    replace_source(conn, source, rows)
