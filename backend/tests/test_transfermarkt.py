import math

from app.analytics import ml
from app.etl import transfermarkt as tm
from tests.conftest import load, make_match


CLUBS = [
    {"club_id": "11", "name": "Arsenal FC", "domestic_competition_id": "GB1"},
    {"club_id": "985", "name": "Manchester United FC", "domestic_competition_id": "GB1"},
    {"club_id": "5", "name": "Some MLS Club", "domestic_competition_id": "MLS1"},
]
VALUATIONS = [
    # Two players at Arsenal in Q1; one revalued within the quarter (latest wins).
    {"player_id": "p1", "date": "2024-01-10", "market_value_in_eur": "50000000", "current_club_id": "11"},
    {"player_id": "p1", "date": "2024-02-20", "market_value_in_eur": "60000000", "current_club_id": "11"},
    {"player_id": "p2", "date": "2024-03-01", "market_value_in_eur": "40000000", "current_club_id": "11"},
    {"player_id": "p3", "date": "2024-02-11", "market_value_in_eur": "30000000", "current_club_id": "985"},
    # Non-top-5 club is ignored.
    {"player_id": "p4", "date": "2024-02-11", "market_value_in_eur": "10000000", "current_club_id": "5"},
    # Malformed rows are skipped.
    {"player_id": "p5", "date": "", "market_value_in_eur": "1", "current_club_id": "11"},
    {"player_id": "p6", "date": "2024-02-11", "market_value_in_eur": "", "current_club_id": "11"},
]


def test_aggregate_quarterly_squad_values():
    rows = tm.aggregate(VALUATIONS, CLUBS)
    by_key = {(r[0], r[1], r[2]): r[3] for r in rows}
    # p1 latest (60M) + p2 (40M) = 100M for Arsenal in 2024 Q1.
    assert by_key[("en.1", "Arsenal", "2024-03-31")] == 100_000_000
    assert by_key[("en.1", "Manchester United", "2024-03-31")] == 30_000_000
    assert all(g == "en.1" for g, *_ in rows)  # MLS club excluded


def test_quarter_end():
    assert tm.quarter_end("2024-01-10") == "2024-03-31"
    assert tm.quarter_end("2024-12-31") == "2024-12-31"
    assert tm.quarter_end("2024-07-01") == "2024-09-30"


def test_mv_feature_nan_without_data_and_active_with(conn):
    rows = []
    import datetime as dt
    day = dt.date(2024, 1, 1)
    for _ in range(12):
        for h, a in (("Arsenal", "Manchester United"), ("Manchester United", "Arsenal")):
            rows.append(make_match(h, a, 1, 0, date=day.isoformat()))
            day += dt.timedelta(days=6)  # runs past the 2024-03-31 snapshot
    load(conn, rows)

    X, *_ = ml.build_dataset(conn, "en.1")
    i = ml.FEATURES.index("mv_log_ratio")
    assert all(math.isnan(x[i]) for x in X)  # empty table -> NaN everywhere

    tm.replace(conn, tm.aggregate(VALUATIONS, CLUBS))
    X2, *_ = ml.build_dataset(conn, "en.1")
    active = [x[i] for x in X2 if not math.isnan(x[i])]
    assert active  # matches after 2024-03-31 get a value
    assert abs(max(active) - math.log(100 / 30)) < 1e-9