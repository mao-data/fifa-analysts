"""Walk-forward backtest of the Elo-based forecast.

Matches are replayed chronologically. For every match inside the test window
(the most recent two years) we forecast *before* updating ratings, using only
information available at that point: the Elo expectation plus the draw rate
observed so far. Reported metrics: 3-way accuracy and multiclass Brier score
(0 = perfect, lower is better), against an always-home-win baseline."""
import datetime as dt
from collections import defaultdict

from . import elo

TEST_WINDOW_DAYS = 2 * 365
MIN_TRAIN_MATCHES = 200


def _wdl_from_elo(e: float, draw_rate: float) -> tuple[float, float, float]:
    w = min(max(e - 0.5 * draw_rate, 0.001), 1.0 - draw_rate - 0.001)
    return w, draw_rate, 1.0 - draw_rate - w


def run_group(conn, group: str) -> dict | None:
    matches = elo.iter_group_matches(conn, group).fetchall()
    if len(matches) < MIN_TRAIN_MATCHES * 2:
        return None
    last = dt.date.fromisoformat(matches[-1]["date"])
    test_from = (last - dt.timedelta(days=TEST_WINDOW_DAYS)).isoformat()

    is_intl = group == "international"
    home_adv = elo.HOME_ADV_INTL if is_intl else elo.HOME_ADV_LEAGUE
    ratings: dict[str, float] = defaultdict(lambda: elo.BASE_ELO)
    seen = draws = home_wins = 0
    n = correct = 0
    brier = baseline_brier = 0.0
    base_correct = 0

    for m in matches:
        h, a = m["home_team"], m["away_team"]
        hs, as_ = m["home_score"], m["away_score"]
        outcome = 0 if hs > as_ else (1 if hs == as_ else 2)  # W/D/L index

        if m["date"] >= test_from and seen >= MIN_TRAIN_MATCHES:
            draw_rate = draws / seen
            e = elo.expected_score(
                elo.rating_diff(ratings[h], ratings[a], bool(m["neutral"]), home_adv))
            probs = _wdl_from_elo(e, draw_rate)
            pred = max(range(3), key=lambda i: probs[i])
            n += 1
            correct += pred == outcome
            base_correct += outcome == 0
            actual = [0.0, 0.0, 0.0]
            actual[outcome] = 1.0
            brier += sum((p - y) ** 2 for p, y in zip(probs, actual))
            base_probs = (home_wins / seen, draws / seen, 1 - (home_wins + draws) / seen)
            baseline_brier += sum((p - y) ** 2 for p, y in zip(base_probs, actual))

        k = elo.k_for_international(m["competition"]) if is_intl else elo.K_LEAGUE
        ratings[h], ratings[a] = elo.update(
            ratings[h], ratings[a], hs, as_, bool(m["neutral"]), k, home_adv)
        seen += 1
        draws += outcome == 1
        home_wins += outcome == 0

    if not n:
        return None
    return {
        "rating_group": group,
        "test_from": test_from,
        "n_matches": n,
        "accuracy": round(correct / n, 4),
        "brier": round(brier / n, 4),
        "baseline_home_accuracy": round(base_correct / n, 4),
        "baseline_brier": round(baseline_brier / n, 4),
        "draw_rate": round(draws / seen, 4),
    }


def run_all(conn) -> list[dict]:
    groups = [r["rating_group"] for r in
              conn.execute("SELECT DISTINCT rating_group FROM matches")]
    results = []
    with conn:
        conn.execute("DELETE FROM backtest_results")
        for g in groups:
            res = run_group(conn, g)
            if not res:
                continue
            results.append(res)
            conn.execute(
                """INSERT INTO backtest_results (rating_group, test_from, n_matches,
                       accuracy, brier, baseline_home_accuracy, baseline_brier, draw_rate)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (res["rating_group"], res["test_from"], res["n_matches"], res["accuracy"],
                 res["brier"], res["baseline_home_accuracy"], res["baseline_brier"],
                 res["draw_rate"]))
    return results
