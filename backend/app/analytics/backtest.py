"""Walk-forward backtest comparing all forecast models on the same matches.

Models evaluated over the most recent two years, none ever seeing the future:
- elo:         Elo expectation + historical draw rate (the simple baseline model)
- dixon_coles: time-decayed attack/defence Poisson with low-score correction,
               refitted every 30 days on data available at that point
- ml:          gradient-boosted trees trained on pre-test-window feature rows
               (the features themselves are walk-forward by construction)
- ensemble:    average of dixon_coles and ml

All models are scored on the identical match set (matches where every model
can produce a forecast), so accuracy and Brier are directly comparable.
Multiclass Brier: 0 = perfect, 2 = worst; baseline always predicts the
training class frequencies / the home team.
"""
import datetime as dt

from . import dixon_coles, elo, ml

TEST_WINDOW_DAYS = 2 * 365
DC_REFIT_DAYS = 30
MIN_TRAIN_ROWS = 300
MODELS = ("elo", "dixon_coles", "ml", "ensemble")


def _wdl_from_elo(e: float, draw_rate: float) -> tuple[float, float, float]:
    w = min(max(e - 0.5 * draw_rate, 0.001), 1.0 - draw_rate - 0.001)
    return w, draw_rate, 1.0 - draw_rate - w


def _brier(probs, outcome: int) -> float:
    return sum((p - (1.0 if i == outcome else 0.0)) ** 2 for i, p in enumerate(probs))


def run_group(conn, group: str) -> tuple[list[dict], list[tuple]]:
    """Returns (per-model metric rows, per-match ensemble predictions).
    Predictions are persisted so the market comparison (analytics/market.py)
    can join them against bookmaker odds later without re-running models."""
    X, y, dates, meta, _ = ml.build_dataset(conn, group)
    if len(X) < MIN_TRAIN_ROWS * 2:
        return [], []
    last = dt.date.fromisoformat(dates[-1])
    test_from = (last - dt.timedelta(days=TEST_WINDOW_DAYS)).isoformat()
    train_idx = [i for i, d in enumerate(dates) if d < test_from]
    test_idx = [i for i, d in enumerate(dates) if d >= test_from]
    if len(train_idx) < MIN_TRAIN_ROWS or not test_idx:
        return [], []

    model = ml.train([X[i] for i in train_idx], [y[i] for i in train_idx])
    ml_probs_all = ml.probs_batch(model, [X[i] for i in test_idx])

    train_y = [y[i] for i in train_idx]
    n_train = len(train_y)
    draw_rate = train_y.count(1) / n_train
    base_probs = (train_y.count(0) / n_train, draw_rate, train_y.count(2) / n_train)
    home_adv = elo.HOME_ADV_INTL if group == "international" else elo.HOME_ADV_LEAGUE

    stats = {m: {"n": 0, "correct": 0, "brier": 0.0} for m in MODELS}
    base_correct = 0
    base_brier = 0.0
    dc_params = None
    next_refit: dt.date | None = None
    predictions: list[tuple] = []

    for row, mlp in zip(test_idx, ml_probs_all):
        date = dt.date.fromisoformat(dates[row])
        if next_refit is None or date >= next_refit:
            dc_params = dixon_coles.fit_group(conn, group, as_of=date,
                                              before_date=dates[row])
            next_refit = date + dt.timedelta(days=DC_REFIT_DAYS)
        home, away = meta[row]
        neutral = bool(X[row][ml.FEATURES.index("neutral")])
        dc = dixon_coles.predict_probs(dc_params, home, away, neutral) if dc_params else None
        if dc is None:
            continue  # keep the evaluation set identical across models
        dc_probs = dc[0]

        e = elo.expected_score(elo.rating_diff(
            X[row][0], X[row][1], neutral, home_adv))
        elo_probs = _wdl_from_elo(e, draw_rate)
        ens = tuple((a + b) / 2 for a, b in zip(dc_probs, mlp))

        outcome = y[row]
        predictions.append((group, dates[row], home, away,
                            ens[0], ens[1], ens[2], outcome))
        for name, probs in (("elo", elo_probs), ("dixon_coles", dc_probs),
                            ("ml", mlp), ("ensemble", ens)):
            s = stats[name]
            s["n"] += 1
            s["correct"] += max(range(3), key=lambda i: probs[i]) == outcome
            s["brier"] += _brier(probs, outcome)
        base_correct += outcome == 0
        base_brier += _brier(base_probs, outcome)

    results: list[dict] = []
    for name in MODELS:
        s = stats[name]
        if not s["n"]:
            continue
        results.append({
            "rating_group": group,
            "model": name,
            "test_from": test_from,
            "n_matches": s["n"],
            "accuracy": round(s["correct"] / s["n"], 4),
            "brier": round(s["brier"] / s["n"], 4),
            "baseline_home_accuracy": round(base_correct / s["n"], 4),
            "baseline_brier": round(base_brier / s["n"], 4),
            "draw_rate": round(draw_rate, 4),
        })
    return results, predictions


def run_all(conn) -> list[dict]:
    groups = [r["rating_group"] for r in
              conn.execute("SELECT DISTINCT rating_group FROM matches")]
    all_results = []
    with conn:
        conn.execute("DELETE FROM backtest_results")
        conn.execute("DELETE FROM backtest_predictions")
        for g in sorted(groups):
            results, predictions = run_group(conn, g)
            conn.executemany(
                "INSERT OR REPLACE INTO backtest_predictions VALUES (?,?,?,?,?,?,?,?)",
                predictions)
            for res in results:
                all_results.append(res)
                conn.execute(
                    """INSERT INTO backtest_results (rating_group, model, test_from,
                           n_matches, accuracy, brier, baseline_home_accuracy,
                           baseline_brier, draw_rate)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (res["rating_group"], res["model"], res["test_from"],
                     res["n_matches"], res["accuracy"], res["brier"],
                     res["baseline_home_accuracy"], res["baseline_brier"],
                     res["draw_rate"]))
    return all_results
