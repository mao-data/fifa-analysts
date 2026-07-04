"""Combine the Elo expectation with the Poisson scoreline model into one
win/draw/loss forecast.

The Poisson model supplies the shape (including the draw probability and the
score matrix); Elo supplies a second opinion on overall strength. We blend the
two expected scores, keep Poisson's draw probability, and rescale win/loss to
match the blended expectation."""
from . import elo, poisson

ELO_WEIGHT = 0.5


def _elo_rating(conn, group: str, team: str) -> float | None:
    row = conn.execute(
        "SELECT rating FROM elo_ratings WHERE rating_group = ? AND team = ?",
        (group, team),
    ).fetchone()
    return row["rating"] if row else None


def predict(conn, group: str, home: str, away: str, neutral: bool = False) -> dict | None:
    r_home = _elo_rating(conn, group, home)
    r_away = _elo_rating(conn, group, away)
    lams = poisson.estimate_lambdas(conn, group, home, away, neutral=neutral)
    if r_home is None or r_away is None or lams is None:
        return None

    home_adv = elo.HOME_ADV_INTL if group == "international" else elo.HOME_ADV_LEAGUE
    e_elo = elo.expected_score(elo.rating_diff(r_home, r_away, neutral, home_adv))

    lam_home, lam_away = lams
    matrix = poisson.score_matrix(lam_home, lam_away)
    p_win, p_draw, p_loss = poisson.outcome_probs(matrix)
    e_poisson = p_win + 0.5 * p_draw

    e_blend = ELO_WEIGHT * e_elo + (1 - ELO_WEIGHT) * e_poisson
    # Keep the Poisson draw probability; move win/loss mass to hit e_blend.
    w = min(max(e_blend - 0.5 * p_draw, 0.0), 1.0 - p_draw)
    l = 1.0 - p_draw - w

    top_scores = sorted(
        ((matrix[i][j], i, j) for i in range(len(matrix)) for j in range(len(matrix))),
        reverse=True,
    )[:5]
    return {
        "home": home,
        "away": away,
        "group": group,
        "neutral": neutral,
        "elo": {"home": round(r_home, 1), "away": round(r_away, 1),
                "expected_score": round(e_elo, 4)},
        "lambdas": {"home": round(lam_home, 3), "away": round(lam_away, 3)},
        "probabilities": {"home_win": round(w, 4), "draw": round(p_draw, 4),
                          "away_win": round(l, 4)},
        "most_likely_scores": [
            {"score": f"{i}-{j}", "probability": round(p, 4)} for p, i, j in top_scores
        ],
        "score_matrix": [[round(p, 5) for p in row[:6]] for row in matrix[:6]],
    }
