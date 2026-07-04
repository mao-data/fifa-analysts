"""Serve-time forecast: ensemble of the Dixon-Coles model and the
gradient-boosted-tree model, with the simple Elo+Poisson blend as fallback
when a team is too new for the fitted models.

The scoreline matrix always comes from Dixon-Coles when available (the ML
classifier only knows win/draw/loss, not scorelines)."""
from . import dixon_coles, elo, ml, poisson

# Assumed importance of a hypothetical upcoming match (ML feature): a
# competitive international (K=40) or a league match (K=20).
SERVE_IMPORTANCE = {"international": 40.0, "league": 20.0}

_model_cache: dict[str, tuple[float, object]] = {}


def _cached_model(group: str):
    path = ml.model_path(group)
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    hit = _model_cache.get(group)
    if hit and hit[0] == mtime:
        return hit[1]
    model = ml.load_model(group)
    _model_cache[group] = (mtime, model)
    return model


def _elo_rating(conn, group: str, team: str) -> float | None:
    row = conn.execute(
        "SELECT rating FROM elo_ratings WHERE rating_group = ? AND team = ?",
        (group, team),
    ).fetchone()
    return row["rating"] if row else None


def _round3(probs) -> dict:
    w, d, l = probs
    return {"home_win": round(w, 4), "draw": round(d, 4), "away_win": round(l, 4)}


def predict(conn, group: str, home: str, away: str, neutral: bool = False) -> dict | None:
    scope = "international" if group == "international" else "league"
    r_home = _elo_rating(conn, group, home)
    r_away = _elo_rating(conn, group, away)
    if r_home is None or r_away is None:
        return None
    home_adv = elo.HOME_ADV_INTL if scope == "international" else elo.HOME_ADV_LEAGUE
    e_elo = elo.expected_score(elo.rating_diff(r_home, r_away, neutral, home_adv))

    models: dict[str, dict] = {}

    # Dixon-Coles
    dc_probs = matrix = lams = None
    params = dixon_coles.load_params(conn, group)
    if params:
        dc = dixon_coles.predict_probs(params, home, away, neutral)
        if dc:
            dc_probs, matrix, lams = dc
            models["dixon_coles"] = _round3(dc_probs) | {"rho": params["rho"]}

    # Gradient boosting
    ml_probs = None
    model = _cached_model(group)
    if model:
        x = ml.serving_features(conn, group, home, away, neutral,
                                SERVE_IMPORTANCE[scope])
        if x is not None:
            ml_probs = ml.probs(model, x)
            models["ml"] = _round3(ml_probs)

    # Combine, falling back to the simple blend when the fitted models
    # don't know one of the teams.
    if dc_probs and ml_probs:
        final = tuple((a + b) / 2 for a, b in zip(dc_probs, ml_probs))
        model_used = "ensemble (dixon_coles + ml)"
    elif dc_probs or ml_probs:
        final = dc_probs or ml_probs
        model_used = "dixon_coles" if dc_probs else "ml"
    else:
        lams = poisson.estimate_lambdas(conn, group, home, away, neutral=neutral)
        if lams is None:
            return None
        matrix = poisson.score_matrix(*lams)
        p_win, p_draw, p_loss = poisson.outcome_probs(matrix)
        e_blend = 0.5 * e_elo + 0.5 * (p_win + 0.5 * p_draw)
        w = min(max(e_blend - 0.5 * p_draw, 0.0), 1.0 - p_draw)
        final = (w, p_draw, 1.0 - p_draw - w)
        model_used = "elo+poisson (fallback)"
    models["ensemble"] = _round3(final)

    if matrix is None:
        lams = lams or poisson.estimate_lambdas(conn, group, home, away, neutral=neutral)
        if lams:
            matrix = poisson.score_matrix(*lams)

    top_scores = []
    if matrix:
        top_scores = sorted(
            ((matrix[i][j], i, j) for i in range(len(matrix)) for j in range(len(matrix))),
            reverse=True,
        )[:5]

    return {
        "home": home,
        "away": away,
        "group": group,
        "neutral": neutral,
        "model_used": model_used,
        "elo": {"home": round(r_home, 1), "away": round(r_away, 1),
                "expected_score": round(e_elo, 4)},
        "lambdas": {"home": round(lams[0], 3), "away": round(lams[1], 3)} if lams else None,
        "probabilities": _round3(final),
        "models": models,
        "most_likely_scores": [
            {"score": f"{i}-{j}", "probability": round(p, 4)} for p, i, j in top_scores
        ],
        "score_matrix": [[round(p, 5) for p in row[:6]] for row in matrix[:6]] if matrix else None,
    }
