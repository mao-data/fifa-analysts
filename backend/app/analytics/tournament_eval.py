"""Live tournament report card: how the models are doing on a tournament
that is happening right now.

Strictly walk-forward, same discipline as the backtest: the ML model is
trained only on matches before the tournament start, Dixon-Coles is refitted
every 15 days using only matches known at that point, and each match's Elo
features reflect results up to (not including) that match. Re-run on every
ETL refresh, so the report follows the tournament automatically."""
import datetime as dt
import json

from . import dixon_coles as dc
from . import elo, ml
from .metrics import brier, pick

# Tournaments to track. Past ones keep working as historical report cards.
TOURNAMENTS = [
    {"key": "wc2026", "name": "FIFA World Cup 2026", "group": "international",
     "competition": "FIFA World Cup", "since": "2026-06-01"},
]
DC_REFIT_DAYS = 15
MODELS = ("elo", "dixon_coles", "ml", "ensemble")


def run(conn, group: str, competition: str, since: str,
        dataset: tuple | None = None) -> dict | None:
    keys = {(r["date"], r["home_team"], r["away_team"]): (r["home_score"], r["away_score"])
            for r in conn.execute(
                """SELECT date, home_team, away_team, home_score, away_score
                   FROM matches WHERE rating_group = ? AND competition = ? AND date >= ?""",
                (group, competition, since))}
    if not keys:
        return None

    if dataset is None:
        X, y, dates, meta, _ = ml.build_dataset(conn, group)
    else:
        X, y, dates, meta = dataset
    idx = [i for i in range(len(X))
           if dates[i] >= since and (dates[i], meta[i][0], meta[i][1]) in keys]
    train_idx = [i for i in range(len(X)) if dates[i] < since]
    if not idx or len(train_idx) < 300:
        return None

    model = ml.train([X[i] for i in train_idx], [y[i] for i in train_idx])
    ml_probs = ml.probs_batch(model, [X[i] for i in idx])
    train_y = [y[i] for i in train_idx]
    draw_rate = train_y.count(1) / len(train_y)
    freq = (train_y.count(0) / len(train_y), draw_rate, train_y.count(2) / len(train_y))
    home_adv = elo.HOME_ADV_INTL if group == "international" else elo.HOME_ADV_LEAGUE
    neutral_i = ml.FEATURES.index("neutral")

    per_model = {m: {"correct": 0, "brier": 0.0} for m in MODELS}
    matches = []
    params, next_refit = None, None
    dc_rows = dc.load_rows(conn, group)

    for j, i in enumerate(idx):
        date = dt.date.fromisoformat(dates[i])
        if next_refit is None or date >= next_refit:
            params = dc.fit_group(conn, group, as_of=date, before_date=dates[i],
                                  rows=dc_rows)
            next_refit = date + dt.timedelta(days=DC_REFIT_DAYS)
        home, away = meta[i]
        neutral = bool(X[i][neutral_i])
        d = dc.predict_probs(params, home, away, neutral) if params else None
        dc_p = d[0] if d else freq
        e = elo.expected_score(elo.rating_diff(X[i][0], X[i][1], neutral, home_adv))
        w = min(max(e - 0.5 * draw_rate, 0.001), 1 - draw_rate - 0.001)
        probs = {
            "elo": (w, draw_rate, 1 - draw_rate - w),
            "dixon_coles": dc_p,
            "ml": ml_probs[j],
        }
        probs["ensemble"] = tuple(
            (a + b) / 2 for a, b in zip(probs["dixon_coles"], probs["ml"]))

        outcome = y[i]
        for name in MODELS:
            per_model[name]["correct"] += pick(probs[name]) == outcome
            per_model[name]["brier"] += brier(probs[name], outcome)
        hs, as_ = keys[(dates[i], home, away)]
        ens = probs["ensemble"]
        matches.append({
            "date": dates[i], "home": home, "away": away,
            "home_score": hs, "away_score": as_,
            "probs": [round(p, 4) for p in ens],
            "predicted": pick(ens),
            "outcome": outcome,
        })

    n = len(matches)
    outcomes = [m["outcome"] for m in matches]
    calibration = _calibration(matches)
    return {
        "group": group,
        "competition": competition,
        "since": since,
        "computed_at": dt.date.today().isoformat(),
        "n_matches": n,
        "models": {
            name: {"accuracy": round(s["correct"] / n, 4), "brier": round(s["brier"] / n, 4)}
            for name, s in per_model.items()
        },
        "baselines": {
            "frequency_brier": round(sum(brier(freq, o) for o in outcomes) / n, 4),
            "uniform_brier": round(2 / 3, 4),
        },
        "outcome_split": [outcomes.count(0), outcomes.count(1), outcomes.count(2)],
        "calibration": calibration,
        "matches": matches,
    }


def _calibration(matches: list[dict]) -> list[dict]:
    buckets: dict[int, list[bool]] = {}
    for m in matches:
        fav = pick(m["probs"])
        b = int(m["probs"][fav] * 100) // 10 * 10
        buckets.setdefault(b, []).append(fav == m["outcome"])
    return [{"bucket": f"{b}-{b + 9}%", "predicted": (b + 5) / 100,
             "actual": round(sum(hits) / len(hits), 4), "n": len(hits)}
            for b, hits in sorted(buckets.items())]


def run_all(conn, progress=print, datasets: dict | None = None) -> list[str]:
    done = []
    for t in TOURNAMENTS:
        report = run(conn, t["group"], t["competition"], t["since"],
                     dataset=(datasets or {}).get(t["group"]))
        if report is None:
            continue
        report["name"] = t["name"]
        with conn:
            conn.execute("INSERT OR REPLACE INTO model_reports (key, report) VALUES (?, ?)",
                         (t["key"], json.dumps(report)))
        ens = report["models"]["ensemble"]
        progress(f"[report] {t['name']}: n={report['n_matches']} "
                 f"ensemble acc={ens['accuracy']:.3f} brier={ens['brier']:.3f}")
        done.append(t["key"])
    return done


def load_all(conn) -> list[dict]:
    return [json.loads(r["report"]) | {"key": r["key"]} for r in
            conn.execute("SELECT key, report FROM model_reports ORDER BY key")]
