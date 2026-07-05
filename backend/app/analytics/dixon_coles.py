"""Dixon-Coles (1997) time-decayed Poisson model.

Each team gets a multiplicative attack and defence strength, fitted by
weighted maximum likelihood where a match's weight decays exponentially
with age — recent form counts more than old results. A global home-advantage
factor applies when the venue isn't neutral, and the signature Dixon-Coles
correction (rho) fixes the known Poisson bias on low-scoring results
(0-0, 1-0, 0-1, 1-1).

Fitting uses the standard iterative multiplicative updates (each step is the
exact weighted-MLE solution for one parameter family given the others), which
converges quickly without an external optimiser; rho is then a 1-D grid
search on the weighted log-likelihood.
"""
import datetime as dt
import json
import math
from collections import defaultdict

from .poisson import poisson_pmf, outcome_probs

# Decay rate per day: leagues turn squads over faster than national sides.
XI = {"international": 0.0012, "league": 0.0030}
# Ignore matches whose weight would be < ~1%.
MAX_AGE_DAYS = {"international": 3800, "league": 1550}
MIN_TEAM_WEIGHT = 3.0  # effective matches needed before we trust a team's fit
ITERATIONS = 60
RHO_GRID = [x / 100 for x in range(-30, 16)]  # -0.30 … 0.15


def _scope(group: str) -> str:
    return "international" if group == "international" else "league"


def fit(matches, as_of: dt.date, scope: str) -> dict | None:
    """matches: iterable of (date_iso, home, away, hs, as_, neutral).
    Returns {'attack': {}, 'defence': {}, 'home_adv': float, 'rho': float}."""
    xi = XI[scope]
    max_age = MAX_AGE_DAYS[scope]
    rows = []
    for date, home, away, hs, as_, neutral in matches:
        age = (as_of - dt.date.fromisoformat(date)).days
        if age < 0 or age > max_age:
            continue
        rows.append((math.exp(-xi * age), home, away, hs, as_, bool(neutral)))
    if len(rows) < 50:
        return None

    teams = {t for _, h, a, *_ in rows for t in (h, a)}
    attack = {t: 1.0 for t in teams}
    defence = {t: 1.0 for t in teams}
    home_adv = 1.2

    for _ in range(ITERATIONS):
        num = defaultdict(float)
        den = defaultdict(float)
        for w, h, a, hs, as_, neutral in rows:
            g = 1.0 if neutral else home_adv
            num[h] += w * hs
            den[h] += w * defence[a] * g
            num[a] += w * as_
            den[a] += w * defence[h]
        # Floor keeps teams that never scored/never conceded in the window
        # from collapsing a rate to zero (log-likelihood needs lambda > 0).
        new_attack = {t: max(num[t] / den[t], 0.01) if den[t] else attack[t]
                      for t in teams}

        num.clear(); den.clear()
        for w, h, a, hs, as_, neutral in rows:
            g = 1.0 if neutral else home_adv
            num[h] += w * as_
            den[h] += w * new_attack[a]
            num[a] += w * hs
            den[a] += w * new_attack[h] * g
        new_defence = {t: max(num[t] / den[t], 0.01) if den[t] else defence[t]
                       for t in teams}

        # Identifiability: keep mean defence at 1 (attack absorbs the scale).
        mean_d = sum(new_defence.values()) / len(new_defence)
        defence = {t: d / mean_d for t, d in new_defence.items()}
        attack = {t: a * mean_d for t, a in new_attack.items()}

        ha_num = ha_den = 0.0
        for w, h, a, hs, as_, neutral in rows:
            if neutral:
                continue
            ha_num += w * hs
            ha_den += w * attack[h] * defence[a]
        if ha_den:
            home_adv = ha_num / ha_den

    rho = _fit_rho(rows, attack, defence, home_adv)
    weight = defaultdict(float)
    for w, h, a, *_ in rows:
        weight[h] += w
        weight[a] += w
    return {
        "attack": attack,
        "defence": defence,
        "home_adv": home_adv,
        "rho": rho,
        "team_weight": dict(weight),
    }


def _tau(x: int, y: int, lam: float, mu: float, rho: float) -> float:
    if x == 0 and y == 0:
        return 1 - lam * mu * rho
    if x == 0 and y == 1:
        return 1 + lam * rho
    if x == 1 and y == 0:
        return 1 + mu * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def _fit_rho(rows, attack, defence, home_adv) -> float:
    best_rho, best_ll = 0.0, -math.inf
    for rho in RHO_GRID:
        ll = 0.0
        ok = True
        for w, h, a, hs, as_, neutral in rows:
            lam = max(attack[h] * defence[a] * (1.0 if neutral else home_adv), 1e-4)
            mu = max(attack[a] * defence[h], 1e-4)
            tau = _tau(hs, as_, lam, mu, rho)
            if tau <= 0:
                ok = False
                break
            ll += w * (math.log(tau)
                       + hs * math.log(lam) - lam - _log_fact(hs)
                       + as_ * math.log(mu) - mu - _log_fact(as_))
        if ok and ll > best_ll:
            best_ll, best_rho = ll, rho
    return best_rho


_LOG_FACT = [0.0]
for _i in range(1, 30):
    _LOG_FACT.append(_LOG_FACT[-1] + math.log(_i))


def _log_fact(n: int) -> float:
    return _LOG_FACT[n] if n < len(_LOG_FACT) else math.lgamma(n + 1)


def lambdas(params: dict, home: str, away: str, neutral: bool) -> tuple[float, float] | None:
    tw = params["team_weight"]
    for t in (home, away):
        if t not in params["attack"] or tw.get(t, 0.0) < MIN_TEAM_WEIGHT:
            return None
    lam = params["attack"][home] * params["defence"][away] * (1.0 if neutral else params["home_adv"])
    mu = params["attack"][away] * params["defence"][home]
    return max(0.05, min(6.0, lam)), max(0.05, min(6.0, mu))


def score_matrix(lam: float, mu: float, rho: float, max_goals: int = 10) -> list[list[float]]:
    m = [[poisson_pmf(lam, i) * poisson_pmf(mu, j) * _tau(i, j, lam, mu, rho)
          for j in range(max_goals + 1)] for i in range(max_goals + 1)]
    total = sum(sum(r) for r in m)
    return [[p / total for p in row] for row in m]


def predict_probs(params: dict, home: str, away: str, neutral: bool):
    """Returns ((w, d, l), matrix, (lam, mu)) or None if a team is unknown."""
    lm = lambdas(params, home, away, neutral)
    if lm is None:
        return None
    lam, mu = lm
    matrix = score_matrix(lam, mu, params["rho"])
    return outcome_probs(matrix), matrix, (lam, mu)


# ---------------------------------------------------------------- persistence

def load_rows(conn, group: str) -> list[tuple]:
    """Match tuples for fit(); load once and reuse across walk-forward refits."""
    return [(r["date"], r["home_team"], r["away_team"], r["home_score"],
             r["away_score"], r["neutral"]) for r in conn.execute(
        "SELECT date, home_team, away_team, home_score, away_score, neutral "
        "FROM matches WHERE rating_group = ?", (group,))]


def fit_group(conn, group: str, as_of: dt.date | None = None,
              before_date: str | None = None,
              rows: list[tuple] | None = None) -> dict | None:
    """Fit on a group's matches (optionally only those strictly before a
    cutoff date, for walk-forward backtesting). Pass preloaded `rows` from
    load_rows() to avoid re-querying on every refit."""
    if rows is None:
        rows = load_rows(conn, group)
    if before_date:
        rows = [r for r in rows if r[0] < before_date]
    if not rows:
        return None
    if as_of is None:
        as_of = dt.date.fromisoformat(max(r[0] for r in rows))
    return fit(rows, as_of, _scope(group))


def save_params(conn, group: str, params: dict) -> None:
    with conn:
        conn.execute("DELETE FROM dc_params WHERE rating_group = ?", (group,))
        conn.execute(
            "INSERT INTO dc_params (rating_group, params) VALUES (?, ?)",
            (group, json.dumps(params)))


def load_params(conn, group: str) -> dict | None:
    row = conn.execute(
        "SELECT params FROM dc_params WHERE rating_group = ?", (group,)).fetchone()
    return json.loads(row["params"]) if row else None
