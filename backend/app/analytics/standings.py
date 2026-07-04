"""League tables computed from raw results (3/1/0 points, goal difference,
then goals scored as tie-breakers)."""


def table(conn, group: str, season: str) -> list[dict]:
    rows = conn.execute(
        """SELECT home_team, away_team, home_score, away_score
           FROM matches WHERE rating_group = ? AND season = ?
           ORDER BY date, id""",
        (group, season),
    ).fetchall()
    teams: dict[str, dict] = {}

    def entry(t: str) -> dict:
        return teams.setdefault(t, {
            "team": t, "played": 0, "wins": 0, "draws": 0, "losses": 0,
            "goals_for": 0, "goals_against": 0, "points": 0, "form": [],
        })

    for m in rows:
        h, a = entry(m["home_team"]), entry(m["away_team"])
        hs, as_ = m["home_score"], m["away_score"]
        for side, gf, ga in ((h, hs, as_), (a, as_, hs)):
            side["played"] += 1
            side["goals_for"] += gf
            side["goals_against"] += ga
        if hs > as_:
            h["wins"] += 1; a["losses"] += 1
            h["points"] += 3
            h["form"].append("W"); a["form"].append("L")
        elif hs < as_:
            a["wins"] += 1; h["losses"] += 1
            a["points"] += 3
            a["form"].append("W"); h["form"].append("L")
        else:
            h["draws"] += 1; a["draws"] += 1
            h["points"] += 1; a["points"] += 1
            h["form"].append("D"); a["form"].append("D")

    out = sorted(
        teams.values(),
        key=lambda t: (t["points"], t["goals_for"] - t["goals_against"], t["goals_for"]),
        reverse=True,
    )
    for pos, t in enumerate(out, 1):
        t["position"] = pos
        t["goal_diff"] = t["goals_for"] - t["goals_against"]
        t["form"] = t["form"][-5:]
    return out


def seasons_for(conn, group: str) -> list[str]:
    return [r["season"] for r in conn.execute(
        """SELECT DISTINCT season FROM matches
           WHERE rating_group = ? AND season IS NOT NULL ORDER BY season DESC""",
        (group,),
    )]
