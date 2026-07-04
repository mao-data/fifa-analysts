"""Poisson goal model: estimate expected goals for each side from recent
attack/defence strength, then turn the scoreline probability matrix into
win/draw/loss probabilities."""
import datetime as dt
from math import exp

MAX_GOALS = 10
LAMBDA_MIN, LAMBDA_MAX = 0.2, 4.5
# Recent-form window used to estimate strengths.
WINDOW_DAYS = {"international": 4 * 365, "league": 2 * 365}


def poisson_pmf(lam: float, k: int) -> float:
    p = exp(-lam)
    for i in range(1, k + 1):
        p *= lam / i
    return p


def score_matrix(lam_home: float, lam_away: float, max_goals: int = MAX_GOALS) -> list[list[float]]:
    ph = [poisson_pmf(lam_home, k) for k in range(max_goals + 1)]
    pa = [poisson_pmf(lam_away, k) for k in range(max_goals + 1)]
    return [[ph[i] * pa[j] for j in range(max_goals + 1)] for i in range(max_goals + 1)]


def outcome_probs(matrix: list[list[float]]) -> tuple[float, float, float]:
    """(home win, draw, away win), renormalised over the truncated matrix."""
    w = d = l = 0.0
    for i, row in enumerate(matrix):
        for j, p in enumerate(row):
            if i > j:
                w += p
            elif i == j:
                d += p
            else:
                l += p
    total = w + d + l
    return w / total, d / total, l / total


def _clamp(lam: float) -> float:
    return max(LAMBDA_MIN, min(LAMBDA_MAX, lam))


def estimate_lambdas(conn, group: str, home: str, away: str,
                     neutral: bool = False) -> tuple[float, float] | None:
    """Classic attack/defence-strength estimate over a recent window.
    Returns None when either team has no recent matches in the group."""
    scope = "international" if group == "international" else "league"
    last = conn.execute(
        "SELECT MAX(date) AS d FROM matches WHERE rating_group = ?", (group,)
    ).fetchone()["d"]
    if not last:
        return None
    since = (dt.date.fromisoformat(last) - dt.timedelta(days=WINDOW_DAYS[scope])).isoformat()

    avg = conn.execute(
        """SELECT AVG(home_score) AS h, AVG(away_score) AS a, COUNT(*) AS n
           FROM matches WHERE rating_group = ? AND date >= ?""",
        (group, since),
    ).fetchone()
    if not avg["n"]:
        return None
    league_home, league_away = avg["h"], avg["a"]
    per_team = (league_home + league_away) / 2.0

    def strengths(team: str) -> tuple[float, float] | None:
        r = conn.execute(
            """SELECT COUNT(*) AS n,
                      AVG(CASE WHEN home_team = :t THEN home_score ELSE away_score END) AS scored,
                      AVG(CASE WHEN home_team = :t THEN away_score ELSE home_score END) AS conceded
               FROM matches
               WHERE rating_group = :g AND date >= :since
                 AND (home_team = :t OR away_team = :t)""",
            {"t": team, "g": group, "since": since},
        ).fetchone()
        if not r["n"]:
            return None
        return r["scored"] / per_team, r["conceded"] / per_team

    sh, sa = strengths(home), strengths(away)
    if sh is None or sa is None:
        return None
    attack_h, defence_h = sh
    attack_a, defence_a = sa
    if neutral:
        base = per_team
        return _clamp(base * attack_h * defence_a), _clamp(base * attack_a * defence_h)
    return (_clamp(league_home * attack_h * defence_a),
            _clamp(league_away * attack_a * defence_h))
