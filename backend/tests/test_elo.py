from app.analytics import elo
from tests.conftest import load, make_match


def test_expected_score_symmetry():
    assert elo.expected_score(0) == 0.5
    assert abs(elo.expected_score(100) + elo.expected_score(-100) - 1.0) < 1e-9
    assert elo.expected_score(400) > 0.9


def test_update_zero_sum_and_direction():
    h, a = elo.update(1500, 1500, 2, 0, neutral=True, k=20, home_adv=100)
    assert h > 1500 > a
    assert abs((h - 1500) + (a - 1500)) < 1e-9  # zero-sum


def test_upset_moves_more_points():
    # An underdog win must shift more rating than a favourite win.
    fav_win_h, _ = elo.update(1700, 1300, 1, 0, True, 20, 100)
    upset_h, _ = elo.update(1300, 1700, 1, 0, True, 20, 100)
    assert (upset_h - 1300) > (fav_win_h - 1700)


def test_mov_multiplier():
    assert elo.mov_multiplier(1) == 1.0
    assert elo.mov_multiplier(2) == 1.5
    assert elo.mov_multiplier(3) == 1.75
    assert elo.mov_multiplier(5) == 2.0
    assert elo.mov_multiplier(-2) == 1.5  # away blowout counts too


def test_home_advantage_reduces_home_gain():
    # Same result, but the home side was expected to win — smaller reward.
    with_adv, _ = elo.update(1500, 1500, 1, 0, neutral=False, k=20, home_adv=100)
    neutral, _ = elo.update(1500, 1500, 1, 0, neutral=True, k=20, home_adv=100)
    assert with_adv < neutral


def test_k_for_international():
    assert elo.k_for_international("FIFA World Cup") == 60
    assert elo.k_for_international("FIFA World Cup qualification") == 40
    assert elo.k_for_international("UEFA Euro") == 50
    assert elo.k_for_international("UEFA Euro qualification") == 40
    assert elo.k_for_international("Friendly") == 20
    assert elo.k_for_international("Copa América") == 50


def test_rebuild_group_persists_history_and_ratings(conn):
    load(conn, [
        make_match("A", "B", 3, 0, date="2024-01-01"),
        make_match("B", "A", 0, 1, date="2024-01-08"),
        make_match("A", "C", 1, 1, date="2024-01-15"),
    ])
    ratings = elo.rebuild_group(conn, "en.1")
    assert ratings["A"] > elo.BASE_ELO > ratings["B"]
    # Two snapshot rows per match.
    n_hist = conn.execute("SELECT COUNT(*) AS n FROM elo_history").fetchone()["n"]
    assert n_hist == 6
    row = conn.execute(
        "SELECT rating, matches FROM elo_ratings WHERE rating_group='en.1' AND team='A'"
    ).fetchone()
    assert row["matches"] == 3
    assert abs(row["rating"] - ratings["A"]) < 1e-9
    # Rebuild is idempotent.
    elo.rebuild_group(conn, "en.1")
    assert conn.execute("SELECT COUNT(*) AS n FROM elo_history").fetchone()["n"] == 6
