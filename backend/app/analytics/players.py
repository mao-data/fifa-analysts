"""Player-level analytics from the international goalscorers data.

Own goals are excluded from a player's tally (they're credited against the
conceding side in the source data, not to a real scorer identity)."""


def top_scorers(conn, team: str | None = None, limit: int = 30,
                since: str | None = None) -> list[dict]:
    where = ["own_goal = 0"]
    params: list = []
    if team:
        where.append("team = ?")
        params.append(team)
    if since:
        where.append("date >= ?")
        params.append(since)
    rows = conn.execute(
        f"""SELECT scorer, team, COUNT(*) AS goals,
               SUM(penalty) AS penalties,
               MIN(date) AS first_goal, MAX(date) AS last_goal
           FROM goals WHERE {' AND '.join(where)}
           GROUP BY scorer, team ORDER BY goals DESC, last_goal DESC
           LIMIT ?""",
        (*params, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def player_profile(conn, scorer: str) -> dict | None:
    total = conn.execute(
        """SELECT COUNT(*) AS goals, SUM(penalty) AS penalties, team,
                  MIN(date) AS first_goal, MAX(date) AS last_goal
           FROM goals WHERE scorer = ? AND own_goal = 0""",
        (scorer,),
    ).fetchone()
    if not total["goals"]:
        return None
    # Minute histogram in 15' buckets (90' plus stoppage folded into the last).
    buckets = [0] * 6
    for r in conn.execute(
            "SELECT minute FROM goals WHERE scorer = ? AND own_goal = 0 "
            "AND minute IS NOT NULL", (scorer,)):
        buckets[min(5, (r["minute"] - 1) // 15 if r["minute"] > 0 else 0)] += 1
    opponents = conn.execute(
        """SELECT CASE WHEN home_team = team THEN away_team ELSE home_team END AS opponent,
                  COUNT(*) AS goals
           FROM goals WHERE scorer = ? AND own_goal = 0
           GROUP BY opponent ORDER BY goals DESC LIMIT 10""",
        (scorer,),
    ).fetchall()
    return {
        "scorer": scorer,
        "team": total["team"],
        "goals": total["goals"],
        "penalties": total["penalties"] or 0,
        "first_goal": total["first_goal"],
        "last_goal": total["last_goal"],
        "minute_distribution": [
            {"period": p, "goals": g}
            for p, g in zip(["1-15", "16-30", "31-45", "46-60", "61-75", "76-90+"], buckets)
        ],
        "favourite_opponents": [dict(r) for r in opponents],
    }


def team_scoring(conn, team: str, since: str | None = None) -> dict | None:
    """Team scoring profile incl. concentration: how dependent the side is on
    its top scorer (share of goals) and a Herfindahl index over scorers."""
    where = "team = ? AND own_goal = 0"
    params: list = [team]
    if since:
        where += " AND date >= ?"
        params.append(since)
    rows = conn.execute(
        f"""SELECT scorer, COUNT(*) AS goals FROM goals
           WHERE {where} GROUP BY scorer ORDER BY goals DESC""",
        params,
    ).fetchall()
    if not rows:
        return None
    total = sum(r["goals"] for r in rows)
    shares = [r["goals"] / total for r in rows]
    return {
        "team": team,
        "since": since,
        "total_goals": total,
        "distinct_scorers": len(rows),
        "top_scorers": [dict(r) for r in rows[:15]],
        "top_scorer_share": round(shares[0], 4),
        "concentration_hhi": round(sum(s * s for s in shares), 4),
        "penalty_share": round(conn.execute(
            f"SELECT AVG(penalty + 0.0) AS p FROM goals WHERE {where}", params
        ).fetchone()["p"] or 0.0, 4),
    }
