import datetime as dt

from app.analytics import elo, predict, stats
from tests.conftest import load, make_match


def _league(conn):
    rows = []
    day = dt.date(2024, 1, 1)
    for _ in range(8):
        for h, a, hs, as_ in (("A", "B", 2, 0), ("B", "A", 1, 1),
                              ("A", "C", 3, 1), ("C", "B", 0, 0)):
            rows.append(make_match(h, a, hs, as_, date=day.isoformat()))
            day += dt.timedelta(days=1)
    load(conn, rows)
    elo.rebuild_group(conn, "en.1")


def test_team_stats(conn):
    _league(conn)
    s = stats.team_stats(conn, "en.1", "A")
    assert s["overall"]["played"] == 24
    assert s["overall"]["wins"] == 16
    assert s["overall"]["draws"] == 8
    assert s["home"]["played"] == 16 and s["home"]["wins"] == 16
    assert s["away"]["played"] == 8 and s["away"]["draws"] == 8
    assert len(s["form"]) == 10
    assert stats.team_stats(conn, "en.1", "Nobody") is None


def test_h2h_perspective(conn):
    _league(conn)
    r = stats.h2h(conn, "A", "B")
    assert r["played"] == 16
    assert r["team1_wins"] == 8 and r["draws"] == 8 and r["team2_wins"] == 0
    assert r["matches"][0]["result"] in {"W", "D", "L"}


def test_predict_probabilities_sum_to_one(conn):
    _league(conn)
    res = predict.predict(conn, "en.1", "A", "B")
    assert res is not None
    p = res["probabilities"]
    total = p["home_win"] + p["draw"] + p["away_win"]
    assert abs(total - 1.0) < 1e-3
    assert p["home_win"] > p["away_win"]  # A dominates B in the fixture data
    assert res["elo"]["home"] > res["elo"]["away"]


def test_predict_unknown_team(conn):
    _league(conn)
    assert predict.predict(conn, "en.1", "A", "Nowhere") is None
