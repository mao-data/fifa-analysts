import datetime as dt

from app.analytics import tournament_eval
from tests.conftest import load, make_match


def _fixture(conn):
    """Long regular season, then a 'cup' where A (dominant) keeps winning."""
    rows = []
    day = dt.date(2022, 1, 1)
    for _ in range(90):
        for h, a, hs, as_ in (("A", "B", 2, 0), ("B", "C", 1, 1),
                              ("A", "C", 3, 0), ("C", "A", 0, 2)):
            rows.append(make_match(h, a, hs, as_, date=day.isoformat(),
                                   competition="League"))
            day += dt.timedelta(days=3)
    cup_day = day + dt.timedelta(days=10)
    for i, (h, a, hs, as_) in enumerate((("A", "B", 2, 0), ("A", "C", 1, 0),
                                         ("B", "C", 2, 2), ("A", "B", 3, 1))):
        rows.append(make_match(h, a, hs, as_, competition="Cup",
                               date=(cup_day + dt.timedelta(days=i * 4)).isoformat()))
    load(conn, rows)
    return cup_day.isoformat()


def test_run_produces_report(conn):
    since = _fixture(conn)
    report = tournament_eval.run(conn, "en.1", "Cup", since)
    assert report is not None
    assert report["n_matches"] == 4
    assert set(report["models"]) == {"elo", "dixon_coles", "ml", "ensemble"}
    ens = report["models"]["ensemble"]
    assert 0 <= ens["brier"] <= 2
    # A dominates everything; the model should get A's three wins right.
    assert ens["accuracy"] >= 0.5
    a_matches = [m for m in report["matches"] if m["home"] == "A"]
    assert all(m["probs"][0] > m["probs"][2] for m in a_matches)
    assert sum(b["n"] for b in report["calibration"]) == 4


def test_run_unknown_competition(conn):
    _fixture(conn)
    assert tournament_eval.run(conn, "en.1", "Nonexistent Cup", "2020-01-01") is None
