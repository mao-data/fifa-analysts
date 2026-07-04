"""Aggregations over StatsBomb shot data: xG tables, over/under-performance
("luck"), and per-match shot maps.

xG (expected goals) is the probability a shot becomes a goal, judged from
its situation (location, body part, pressure…). Summing xG gives the score
a team "deserved"; goals minus xG measures finishing over-performance —
positive = clinical/lucky, negative = wasteful/unlucky."""


def competitions(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT competition, season, COUNT(*) AS matches,
                  MIN(date) AS date_from, MAX(date) AS date_to
           FROM sb_matches GROUP BY competition, season
           ORDER BY date_to DESC""")]


def team_table(conn, competition: str, season: str) -> list[dict]:
    rows = conn.execute(
        """SELECT s.team,
                  COUNT(DISTINCT s.match_id) AS matches,
                  COUNT(*) AS shots,
                  SUM(s.xg) AS xg_for,
                  SUM(CASE WHEN s.outcome = 'Goal' THEN 1 ELSE 0 END) AS goals
           FROM sb_shots s JOIN sb_matches m ON m.match_id = s.match_id
           WHERE m.competition = ? AND m.season = ?
           GROUP BY s.team""",
        (competition, season),
    ).fetchall()
    against = {r["team"]: r for r in conn.execute(
        """SELECT CASE WHEN s.team = m.home_team THEN m.away_team ELSE m.home_team END AS team,
                  SUM(s.xg) AS xg_against,
                  SUM(CASE WHEN s.outcome = 'Goal' THEN 1 ELSE 0 END) AS goals_against
           FROM sb_shots s JOIN sb_matches m ON m.match_id = s.match_id
           WHERE m.competition = ? AND m.season = ?
           GROUP BY 1""",
        (competition, season),
    )}
    out = []
    for r in rows:
        a = against.get(r["team"])
        out.append({
            "team": r["team"],
            "matches": r["matches"],
            "shots": r["shots"],
            "goals": r["goals"],
            "xg_for": round(r["xg_for"], 2),
            "goals_against": a["goals_against"] if a else 0,
            "xg_against": round(a["xg_against"], 2) if a else 0.0,
            "finishing_delta": round(r["goals"] - r["xg_for"], 2),
        })
    out.sort(key=lambda t: t["xg_for"] - t["xg_against"], reverse=True)
    return out


def player_table(conn, competition: str, season: str, limit: int = 30) -> list[dict]:
    rows = conn.execute(
        """SELECT s.player, s.team,
                  COUNT(*) AS shots,
                  SUM(s.xg) AS xg,
                  SUM(CASE WHEN s.outcome = 'Goal' THEN 1 ELSE 0 END) AS goals,
                  SUM(CASE WHEN s.play_type = 'Penalty' THEN 1 ELSE 0 END) AS penalty_shots
           FROM sb_shots s JOIN sb_matches m ON m.match_id = s.match_id
           WHERE m.competition = ? AND m.season = ?
           GROUP BY s.player, s.team
           HAVING shots >= 3
           ORDER BY goals DESC, xg DESC LIMIT ?""",
        (competition, season, limit),
    ).fetchall()
    return [{
        "player": r["player"], "team": r["team"], "shots": r["shots"],
        "goals": r["goals"], "xg": round(r["xg"], 2),
        "penalty_shots": r["penalty_shots"],
        "finishing_delta": round(r["goals"] - r["xg"], 2),
    } for r in rows]


def match_list(conn, competition: str, season: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        """SELECT match_id, date, stage, home_team, away_team, home_score,
                  away_score, stadium
           FROM sb_matches WHERE competition = ? AND season = ?
           ORDER BY date, match_id""",
        (competition, season))]


def match_shots(conn, match_id: int) -> dict | None:
    match = conn.execute(
        "SELECT * FROM sb_matches WHERE match_id = ?", (match_id,)).fetchone()
    if not match:
        return None
    shots = [dict(r) for r in conn.execute(
        """SELECT team, player, minute, x, y, xg, outcome, body_part, play_type
           FROM sb_shots WHERE match_id = ? ORDER BY minute""",
        (match_id,))]
    xg_totals: dict[str, float] = {}
    for s in shots:
        xg_totals[s["team"]] = xg_totals.get(s["team"], 0.0) + s["xg"]
    return {
        "match": dict(match),
        "shots": shots,
        "xg_totals": {t: round(v, 2) for t, v in xg_totals.items()},
    }
