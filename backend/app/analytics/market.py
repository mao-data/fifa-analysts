"""Market vs model: compare our stored walk-forward ensemble forecasts with
bookmaker odds on the same matches.

Implied probabilities are margin-stripped (each 1/odds divided by their sum),
so the market numbers are honest probabilities, not prices. The comparison
runs on the intersection of the backtest window and the odds table — both
sides scored on identical matches."""


from .metrics import brier, pick


def _implied(oh: float, od: float, oa: float) -> tuple[float, float, float]:
    inv = (1 / oh, 1 / od, 1 / oa)
    s = sum(inv)
    return inv[0] / s, inv[1] / s, inv[2] / s


def compare(conn, group: str) -> dict | None:
    rows = conn.execute(
        """SELECT b.date, b.home_team, b.away_team, b.p_home, b.p_draw, b.p_away,
                  b.outcome, o.odds_home, o.odds_draw, o.odds_away, o.book
           FROM backtest_predictions b
           JOIN odds o ON o.rating_group = b.rating_group AND o.date = b.date
                      AND o.home_team = b.home_team AND o.away_team = b.away_team
           WHERE b.rating_group = ? ORDER BY b.date""",
        (group,),
    ).fetchall()
    if not rows:
        return None

    n = len(rows)
    stats = {"model": {"correct": 0, "brier": 0.0},
             "market": {"correct": 0, "brier": 0.0}}
    divergences = []
    for r in rows:
        model_p = (r["p_home"], r["p_draw"], r["p_away"])
        market_p = _implied(r["odds_home"], r["odds_draw"], r["odds_away"])
        o = r["outcome"]
        for name, p in (("model", model_p), ("market", market_p)):
            stats[name]["correct"] += pick(p) == o
            stats[name]["brier"] += brier(p, o)
        gap = max(abs(a - b) for a, b in zip(model_p, market_p))
        divergences.append({
            "date": r["date"], "home": r["home_team"], "away": r["away_team"],
            "model": [round(p, 3) for p in model_p],
            "market": [round(p, 3) for p in market_p],
            "gap": round(gap, 3), "outcome": o, "book": r["book"],
        })
    divergences.sort(key=lambda d: d["gap"], reverse=True)
    return {
        "group": group,
        "n_matches": n,
        "model": {"accuracy": round(stats["model"]["correct"] / n, 4),
                  "brier": round(stats["model"]["brier"] / n, 4)},
        "market": {"accuracy": round(stats["market"]["correct"] / n, 4),
                   "brier": round(stats["market"]["brier"] / n, 4)},
        "top_divergences": divergences[:10],
    }


def compare_all(conn) -> list[dict]:
    groups = [r["rating_group"] for r in
              conn.execute("SELECT DISTINCT rating_group FROM backtest_predictions")]
    return [c for g in sorted(groups) if (c := compare(conn, g))]
