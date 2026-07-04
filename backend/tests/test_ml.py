import datetime as dt

from app.analytics import ml
from tests.conftest import load, make_match


def _alternating_league(conn, n=60):
    """A beats B and C consistently; B beats C."""
    rows = []
    day = dt.date(2023, 1, 1)
    for _ in range(n):
        for h, a, hs, as_ in (("A", "B", 2, 0), ("A", "C", 3, 1),
                              ("B", "C", 2, 1), ("C", "A", 0, 2)):
            rows.append(make_match(h, a, hs, as_, date=day.isoformat()))
            day += dt.timedelta(days=2)
    load(conn, rows)


def test_build_dataset_is_walk_forward(conn):
    _alternating_league(conn)
    X, y, dates, meta, serving = ml.build_dataset(conn, "en.1")
    # Early matches (before both teams have 5 priors) are skipped.
    assert len(X) < 240
    assert len(X) == len(y) == len(dates) == len(meta)
    assert dates == sorted(dates)
    # Feature vector shape matches the declared list.
    assert all(len(row) == len(ml.FEATURES) for row in X)
    # A dominates: its Elo feature when at home vs B should exceed B's.
    i = next(k for k, (h, a) in enumerate(meta) if h == "A" and a == "B" and k > 50)
    assert X[i][0] > X[i][1]
    # Serving state has every team with its rolling stats filled.
    assert serving["A"]["n"] >= 10
    assert serving["A"]["gf10"] > serving["C"]["gf10"]


def test_train_and_predict_orders_teams(conn):
    _alternating_league(conn)
    X, y, dates, meta, serving = ml.build_dataset(conn, "en.1")
    model = ml.train(X, y)
    ml.save_serving_state(conn, "en.1", serving)
    x = ml.serving_features(conn, "en.1", "A", "C", neutral=False, importance=20.0)
    assert x is not None
    w, d, l = ml.probs(model, x)
    assert abs(w + d + l - 1.0) < 1e-6
    assert w > l  # A should be favoured over C


def test_serving_features_unknown_team(conn):
    _alternating_league(conn)
    *_, serving = ml.build_dataset(conn, "en.1")
    ml.save_serving_state(conn, "en.1", serving)
    assert ml.serving_features(conn, "en.1", "A", "Nowhere", False, 20.0) is None
