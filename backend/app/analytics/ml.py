"""Gradient-boosted-tree forecast (scikit-learn HistGradientBoosting).

Features are built strictly walk-forward: every row is computed from state
*before* that match was played, so training never leaks the future. The same
walker produces the end-of-data serving state (persisted to `ml_team_state`)
so request-time predictions use exactly the features the model was trained on.

Feature vector (order matters — serving must match training):
    elo_h, elo_a, elo_diff_adj, form5_h, form5_a,
    gf10_h, ga10_h, gf10_a, ga10_a, rest_h, rest_a, neutral, importance,
    mv_log_ratio

mv_log_ratio is log(home squad market value / away's) from the transfermarkt
table when populated; NaN otherwise — HistGradientBoosting handles missing
values natively, so the feature silently activates once the data exists.
"""
import datetime as dt
import math
from bisect import bisect_right
from collections import defaultdict, deque
from pathlib import Path

from . import elo

FEATURES = ["elo_h", "elo_a", "elo_diff_adj", "form5_h", "form5_a",
            "gf10_h", "ga10_h", "gf10_a", "ga10_a", "rest_h", "rest_a",
            "neutral", "importance", "mv_log_ratio"]
MIN_PRIOR_MATCHES = 5
REST_CAP = 60.0
MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "models"
CLASSES = [0, 1, 2]  # home win / draw / away win


class _TeamState:
    __slots__ = ("results", "goals", "last_date")

    def __init__(self):
        self.results = deque(maxlen=5)   # points per match: 3/1/0
        self.goals = deque(maxlen=10)    # (scored, conceded)
        self.last_date: dt.date | None = None


def _rest(state: _TeamState, date: dt.date) -> float:
    if state.last_date is None:
        return REST_CAP
    return min(REST_CAP, float((date - state.last_date).days))


class MarketValues:
    """Point-in-time squad-value lookup (empty table -> always NaN)."""

    def __init__(self, conn, group: str):
        self.by_team: dict[str, tuple[list[str], list[float]]] = {}
        for r in conn.execute(
                """SELECT team, date, squad_value FROM market_values
                   WHERE rating_group = ? ORDER BY team, date""", (group,)):
            dates, values = self.by_team.setdefault(r["team"], ([], []))
            dates.append(r["date"])
            values.append(r["squad_value"])

    def value(self, team: str, date_iso: str) -> float | None:
        entry = self.by_team.get(team)
        if not entry:
            return None
        i = bisect_right(entry[0], date_iso)
        return entry[1][i - 1] if i else None

    def log_ratio(self, home: str, away: str, date_iso: str) -> float:
        vh, va = self.value(home, date_iso), self.value(away, date_iso)
        if not vh or not va:
            return math.nan
        return math.log(vh / va)


def _features(ratings, st_h: _TeamState, st_a: _TeamState, date: dt.date,
              home: str, away: str, neutral: bool, importance: float,
              home_adv: float, mv_log_ratio: float = math.nan) -> list[float]:
    gf10_h = sum(g for g, _ in st_h.goals) / len(st_h.goals)
    ga10_h = sum(c for _, c in st_h.goals) / len(st_h.goals)
    gf10_a = sum(g for g, _ in st_a.goals) / len(st_a.goals)
    ga10_a = sum(c for _, c in st_a.goals) / len(st_a.goals)
    return [
        ratings[home], ratings[away],
        elo.rating_diff(ratings[home], ratings[away], neutral, home_adv),
        sum(st_h.results) / len(st_h.results),
        sum(st_a.results) / len(st_a.results),
        gf10_h, ga10_h, gf10_a, ga10_a,
        _rest(st_h, date), _rest(st_a, date),
        float(neutral), importance, mv_log_ratio,
    ]


def build_dataset(conn, group: str):
    """Walk the group chronologically. Returns (X, y, dates, meta, serving)
    where meta holds (home, away) per row and serving maps team -> current
    feature ingredients."""
    is_intl = group == "international"
    home_adv = elo.HOME_ADV_INTL if is_intl else elo.HOME_ADV_LEAGUE
    ratings: dict[str, float] = defaultdict(lambda: elo.BASE_ELO)
    states: dict[str, _TeamState] = defaultdict(_TeamState)
    X: list[list[float]] = []
    y: list[int] = []
    dates: list[str] = []
    meta: list[tuple[str, str]] = []
    mv = MarketValues(conn, group)

    for m in elo.iter_group_matches(conn, group).fetchall():
        h, a = m["home_team"], m["away_team"]
        hs, as_ = m["home_score"], m["away_score"]
        neutral = bool(m["neutral"])
        k = elo.k_for_international(m["competition"]) if is_intl else elo.K_LEAGUE
        date = dt.date.fromisoformat(m["date"])
        st_h, st_a = states[h], states[a]

        if len(st_h.goals) >= MIN_PRIOR_MATCHES and len(st_a.goals) >= MIN_PRIOR_MATCHES:
            X.append(_features(ratings, st_h, st_a, date, h, a, neutral, k, home_adv,
                               mv.log_ratio(h, a, m["date"])))
            y.append(0 if hs > as_ else (1 if hs == as_ else 2))
            dates.append(m["date"])
            meta.append((h, a))

        # Update state after the match.
        ratings[h], ratings[a] = elo.update(ratings[h], ratings[a], hs, as_, neutral, k, home_adv)
        st_h.results.append(3 if hs > as_ else (1 if hs == as_ else 0))
        st_a.results.append(3 if as_ > hs else (1 if hs == as_ else 0))
        st_h.goals.append((hs, as_))
        st_a.goals.append((as_, hs))
        st_h.last_date = st_a.last_date = date

    serving = {
        t: {
            "elo": ratings[t],
            "form5": sum(s.results) / len(s.results) if s.results else None,
            "gf10": sum(g for g, _ in s.goals) / len(s.goals) if s.goals else None,
            "ga10": sum(c for _, c in s.goals) / len(s.goals) if s.goals else None,
            "last_date": s.last_date.isoformat() if s.last_date else None,
            "n": len(s.goals),
        }
        for t, s in states.items()
    }
    return X, y, dates, meta, serving


def make_model():
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
        early_stopping=True, validation_fraction=0.1, random_state=42)


def _all_nan_columns(X) -> list[int]:
    n_cols = len(X[0])
    return [j for j in range(n_cols) if all(math.isnan(row[j]) for row in X)]


def _zero_fill(x: list[float], cols: list[int]) -> list[float]:
    if not cols:
        return x
    out = list(x)
    for j in cols:
        if math.isnan(out[j]):
            out[j] = 0.0
    return out


def train(X, y):
    """Columns that are entirely NaN (e.g. mv_log_ratio before the
    transfermarkt data is loaded) crash sklearn's binning — zero-fill them and
    remember which, so serving applies the same treatment."""
    model = make_model()
    nan_cols = _all_nan_columns(X)
    model.all_nan_cols_ = nan_cols
    model.fit([_zero_fill(row, nan_cols) for row in X], y)
    return model


def probs_batch(model, X) -> list[tuple[float, float, float]]:
    """(home win, draw, away win) rows regardless of which classes were seen."""
    cols = getattr(model, "all_nan_cols_", [])
    P = model.predict_proba([_zero_fill(row, cols) for row in X])
    pos = {c: j for j, c in enumerate(model.classes_)}
    return [tuple(row[pos[c]] if c in pos else 0.0 for c in CLASSES) for row in P]


def probs(model, x: list[float]) -> tuple[float, float, float]:
    return probs_batch(model, [x])[0]


# ---------------------------------------------------------------- persistence

def model_path(group: str) -> Path:
    return MODELS_DIR / f"{group}.joblib"


def save_model(model, group: str) -> None:
    import joblib
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path(group))


def load_model(group: str):
    import joblib
    path = model_path(group)
    return joblib.load(path) if path.exists() else None


def save_serving_state(conn, group: str, serving: dict) -> None:
    with conn:
        conn.execute("DELETE FROM ml_team_state WHERE rating_group = ?", (group,))
        conn.executemany(
            """INSERT INTO ml_team_state
                   (rating_group, team, elo, form5, gf10, ga10, last_date, n)
               VALUES (?,?,?,?,?,?,?,?)""",
            [(group, t, s["elo"], s["form5"], s["gf10"], s["ga10"], s["last_date"], s["n"])
             for t, s in serving.items()])


def serving_features(conn, group: str, home: str, away: str,
                     neutral: bool, importance: float) -> list[float] | None:
    home_adv = elo.HOME_ADV_INTL if group == "international" else elo.HOME_ADV_LEAGUE
    rows = {r["team"]: r for r in conn.execute(
        "SELECT * FROM ml_team_state WHERE rating_group = ? AND team IN (?, ?)",
        (group, home, away))}
    h, a = rows.get(home), rows.get(away)
    if not h or not a or h["n"] < MIN_PRIOR_MATCHES or a["n"] < MIN_PRIOR_MATCHES:
        return None
    today = dt.date.today()

    def rest(r) -> float:
        if not r["last_date"]:
            return REST_CAP
        return min(REST_CAP, float((today - dt.date.fromisoformat(r["last_date"])).days))

    mv = MarketValues(conn, group)
    return [
        h["elo"], a["elo"],
        elo.rating_diff(h["elo"], a["elo"], neutral, home_adv),
        h["form5"], a["form5"],
        h["gf10"], h["ga10"], a["gf10"], a["ga10"],
        rest(h), rest(a),
        float(neutral), importance,
        mv.log_ratio(home, away, today.isoformat()),
    ]
