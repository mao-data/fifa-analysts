"""All API routes. SQLite is opened per-request (cheap, and keeps the app
stateless so ETL can rebuild the DB underneath a running server)."""
import sqlite3
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException, Query

from ..analytics import predict as predict_mod
from ..analytics import stats, standings
from ..db import get_conn
from ..etl.leagues import LEAGUES

router = APIRouter(prefix="/api")


def db() -> Iterator[sqlite3.Connection]:
    conn = get_conn()
    try:
        yield conn
    finally:
        conn.close()


GROUPS = {"international": "International", **LEAGUES}


def _check_group(group: str) -> str:
    if group not in GROUPS:
        raise HTTPException(404, f"unknown group '{group}'")
    return group


@router.get("/meta")
def meta(conn=Depends(db)):
    counts = {r["rating_group"]: r["n"] for r in conn.execute(
        "SELECT rating_group, COUNT(*) AS n FROM matches GROUP BY rating_group")}
    date_range = conn.execute("SELECT MIN(date) AS lo, MAX(date) AS hi FROM matches").fetchone()
    return {
        "groups": [
            {
                "id": g,
                "name": name,
                "scope": "international" if g == "international" else "league",
                "matches": counts.get(g, 0),
                "seasons": standings.seasons_for(conn, g) if g != "international" else [],
            }
            for g, name in GROUPS.items()
        ],
        "total_matches": sum(counts.values()),
        "date_range": {"from": date_range["lo"], "to": date_range["hi"]},
    }


@router.get("/matches/recent")
def recent(group: str | None = None, limit: int = Query(20, le=100), conn=Depends(db)):
    if group:
        _check_group(group)
    return stats.recent_matches(conn, group, limit)


@router.get("/teams")
def teams(group: str, q: str | None = None, conn=Depends(db)):
    return stats.list_teams(conn, _check_group(group), q)


@router.get("/teams/{team}/stats")
def team_stats(team: str, group: str, conn=Depends(db)):
    res = stats.team_stats(conn, _check_group(group), team)
    if res is None:
        raise HTTPException(404, f"no matches for '{team}' in '{group}'")
    return res


@router.get("/teams/{team}/elo-history")
def elo_history(team: str, group: str, conn=Depends(db)):
    rows = conn.execute(
        """SELECT date, elo_after FROM elo_history
           WHERE rating_group = ? AND team = ? ORDER BY date, match_id""",
        (_check_group(group), team),
    ).fetchall()
    if not rows:
        raise HTTPException(404, f"no Elo history for '{team}' in '{group}'")
    return {"team": team, "group": group,
            "history": [{"date": r["date"], "elo": round(r["elo_after"], 1)} for r in rows]}


@router.get("/h2h")
def h2h(team1: str, team2: str, group: str | None = None, conn=Depends(db)):
    if group:
        _check_group(group)
    return stats.h2h(conn, team1, team2, group)


@router.get("/standings/{group}/{season}")
def standings_table(group: str, season: str, conn=Depends(db)):
    _check_group(group)
    rows = standings.table(conn, group, season)
    if not rows:
        raise HTTPException(404, f"no matches for {group} season {season}")
    return {"group": group, "season": season, "table": rows}


@router.get("/rankings/elo")
def elo_rankings(group: str, limit: int = Query(50, le=500), min_matches: int = 10,
                 conn=Depends(db)):
    return {"group": _check_group(group),
            "rankings": stats.list_teams(conn, group, min_matches=min_matches)[:limit]}


@router.get("/predict")
def predict(home: str, away: str, group: str, neutral: bool = False, conn=Depends(db)):
    res = predict_mod.predict(conn, _check_group(group), home, away, neutral=neutral)
    if res is None:
        raise HTTPException(
            404, "not enough recent data for one of the teams — check names via /api/teams")
    return res


@router.get("/model/backtest")
def backtest_results(conn=Depends(db)):
    rows = conn.execute("SELECT * FROM backtest_results ORDER BY rating_group").fetchall()
    return {"results": [dict(r) for r in rows],
            "notes": "Walk-forward Elo forecast over the last 2 years; "
                     "brier is multiclass (0 best, 2 worst); baseline always picks home win."}
