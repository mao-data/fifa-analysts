from app.analytics import standings
from tests.conftest import load, make_match


def test_points_and_tiebreakers(conn):
    load(conn, [
        # A beats everyone (6 pts), B and C tie on points → goal difference.
        make_match("A", "B", 2, 0, date="2024-01-01"),
        make_match("A", "C", 1, 0, date="2024-01-08"),
        make_match("B", "C", 3, 1, date="2024-01-15"),
        make_match("C", "B", 2, 1, date="2024-01-22"),
    ])
    table = standings.table(conn, "en.1", "2023-24")
    assert [t["team"] for t in table] == ["A", "B", "C"]
    a, b, c = table
    assert a["points"] == 6 and a["played"] == 2
    assert b["points"] == 3 and c["points"] == 3
    # B scored 0+3+1=4, conceded 2+1+2=5.
    assert b["goals_for"] == 4 and b["goals_against"] == 5
    assert b["goal_diff"] == -1
    # C scored 0+1+2=3, conceded 1+3+1=5 → GD -2 < B's -1, so B ranks above C.
    assert c["goals_for"] == 3 and c["goals_against"] == 5
    assert b["position"] == 2 and c["position"] == 3


def test_form_is_last_five(conn):
    rows = [make_match("A", "B", 1, 0, date=f"2024-01-{d:02d}") for d in range(1, 8)]
    load(conn, rows)
    table = standings.table(conn, "en.1", "2023-24")
    a = next(t for t in table if t["team"] == "A")
    assert a["form"] == ["W"] * 5


def test_seasons_for(conn):
    load(conn, [
        make_match("A", "B", 1, 0, season="2022-23"),
        make_match("A", "B", 1, 0, season="2023-24"),
    ])
    assert standings.seasons_for(conn, "en.1") == ["2023-24", "2022-23"]
