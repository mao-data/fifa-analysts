"""Descriptive stats: win rates, form, goal distribution, head-to-head."""


def _record(conn, group: str, team: str, side: str | None = None) -> dict:
    if side == "home":
        where, params = "home_team = :t", {"g": group, "t": team}
    elif side == "away":
        where, params = "away_team = :t", {"g": group, "t": team}
    else:
        where, params = "(home_team = :t OR away_team = :t)", {"g": group, "t": team}
    r = conn.execute(
        f"""SELECT COUNT(*) AS played,
               SUM(CASE WHEN (home_team = :t AND home_score > away_score)
                          OR (away_team = :t AND away_score > home_score) THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN home_score = away_score THEN 1 ELSE 0 END) AS draws,
               SUM(CASE WHEN home_team = :t THEN home_score ELSE away_score END) AS goals_for,
               SUM(CASE WHEN home_team = :t THEN away_score ELSE home_score END) AS goals_against
           FROM matches WHERE rating_group = :g AND {where}""",
        params,
    ).fetchone()
    played = r["played"] or 0
    wins, draws = r["wins"] or 0, r["draws"] or 0
    return {
        "played": played,
        "wins": wins,
        "draws": draws,
        "losses": played - wins - draws,
        "win_rate": round(wins / played, 4) if played else None,
        "goals_for": r["goals_for"] or 0,
        "goals_against": r["goals_against"] or 0,
    }


def _match_dict(m, perspective: str | None = None) -> dict:
    d = {
        "date": m["date"], "competition": m["competition"], "season": m["season"],
        "home_team": m["home_team"], "away_team": m["away_team"],
        "home_score": m["home_score"], "away_score": m["away_score"],
    }
    if perspective:
        if m["home_score"] == m["away_score"]:
            d["result"] = "D"
        elif (m["home_team"] == perspective) == (m["home_score"] > m["away_score"]):
            d["result"] = "W"
        else:
            d["result"] = "L"
    return d


def team_stats(conn, group: str, team: str, form_n: int = 10) -> dict | None:
    overall = _record(conn, group, team)
    if not overall["played"]:
        return None
    form_rows = conn.execute(
        """SELECT * FROM matches
           WHERE rating_group = ? AND (home_team = ? OR away_team = ?)
           ORDER BY date DESC, id DESC LIMIT ?""",
        (group, team, team, form_n),
    ).fetchall()
    dist_rows = conn.execute(
        """SELECT CASE WHEN home_team = :t THEN home_score ELSE away_score END AS gs,
                  COUNT(*) AS n
           FROM matches WHERE rating_group = :g AND (home_team = :t OR away_team = :t)
           GROUP BY gs ORDER BY gs""",
        {"g": group, "t": team},
    ).fetchall()
    return {
        "team": team,
        "group": group,
        "overall": overall,
        "home": _record(conn, group, team, "home"),
        "away": _record(conn, group, team, "away"),
        "form": [_match_dict(m, team) for m in form_rows],
        "goals_scored_distribution": [{"goals": r["gs"], "matches": r["n"]} for r in dist_rows],
    }


def h2h(conn, team1: str, team2: str, group: str | None = None, limit: int = 20) -> dict:
    where = "((home_team = :t1 AND away_team = :t2) OR (home_team = :t2 AND away_team = :t1))"
    params = {"t1": team1, "t2": team2}
    if group:
        where += " AND rating_group = :g"
        params["g"] = group
    totals = conn.execute(
        f"""SELECT COUNT(*) AS played,
               SUM(CASE WHEN (home_team = :t1 AND home_score > away_score)
                          OR (away_team = :t1 AND away_score > home_score) THEN 1 ELSE 0 END) AS t1_wins,
               SUM(CASE WHEN home_score = away_score THEN 1 ELSE 0 END) AS draws,
               SUM(CASE WHEN home_team = :t1 THEN home_score ELSE away_score END) AS t1_goals,
               SUM(CASE WHEN home_team = :t1 THEN away_score ELSE home_score END) AS t2_goals
           FROM matches WHERE {where}""",
        params,
    ).fetchone()
    matches = conn.execute(
        f"SELECT * FROM matches WHERE {where} ORDER BY date DESC, id DESC LIMIT {int(limit)}",
        params,
    ).fetchall()
    played = totals["played"] or 0
    t1_wins, draws = totals["t1_wins"] or 0, totals["draws"] or 0
    return {
        "team1": team1,
        "team2": team2,
        "played": played,
        "team1_wins": t1_wins,
        "draws": draws,
        "team2_wins": played - t1_wins - draws,
        "team1_goals": totals["t1_goals"] or 0,
        "team2_goals": totals["t2_goals"] or 0,
        "matches": [_match_dict(m, team1) for m in matches],
    }


def list_teams(conn, group: str, q: str | None = None, min_matches: int = 5) -> list[dict]:
    rows = conn.execute(
        """SELECT team, rating, matches, last_date FROM elo_ratings
           WHERE rating_group = ? ORDER BY rating DESC""",
        (group,),
    ).fetchall()
    out = []
    for r in rows:
        if r["matches"] < min_matches:
            continue
        if q and q.lower() not in r["team"].lower():
            continue
        out.append({"team": r["team"], "elo": round(r["rating"], 1),
                    "matches": r["matches"], "last_match": r["last_date"]})
    return out


def recent_matches(conn, group: str | None = None, limit: int = 20) -> list[dict]:
    where, params = "", []
    if group:
        where = "WHERE rating_group = ?"
        params.append(group)
    rows = conn.execute(
        f"SELECT * FROM matches {where} ORDER BY date DESC, id DESC LIMIT ?",
        (*params, limit),
    ).fetchall()
    return [_match_dict(m) | {"group": m["rating_group"]} for m in rows]
