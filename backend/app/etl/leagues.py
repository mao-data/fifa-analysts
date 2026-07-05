"""Top-5 league results from github.com/openfootball/football.json (CC0).
Season files from 2010-11 onwards; matches without a full-time score
(not yet played) are skipped."""
import datetime as dt

from .base import MatchRow, canonical_team_name, make_session

BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master"
SOURCE = "openfootball"

LEAGUES = {
    "en.1": "Premier League",
    "es.1": "La Liga",
    "de.1": "Bundesliga",
    "it.1": "Serie A",
    "fr.1": "Ligue 1",
}
FIRST_SEASON_START = 2010


def seasons(today: dt.date | None = None) -> list[str]:
    today = today or dt.date.today()
    # A season labelled 2025-26 starts in August 2025.
    last_start = today.year if today.month >= 8 else today.year - 1
    return [f"{y}-{str(y + 1)[-2:]}" for y in range(FIRST_SEASON_START, last_start + 1)]


def parse_season_json(data: dict, code: str, season: str) -> list[MatchRow]:
    rows: list[MatchRow] = []
    for m in data.get("matches", []):
        score = m.get("score")
        # Unplayed fixtures have no score dict (or a malformed placeholder).
        if not isinstance(score, dict) or not isinstance(score.get("ft"), list):
            continue
        ft = score["ft"]
        if len(ft) != 2 or ft[0] is None or ft[1] is None:
            continue
        team1, team2 = m.get("team1"), m.get("team2")
        if isinstance(team1, dict):
            team1 = team1.get("name", "")
        if isinstance(team2, dict):
            team2 = team2.get("name", "")
        if not team1 or not team2 or not m.get("date"):
            continue
        rows.append(MatchRow(
            source=SOURCE,
            scope="league",
            rating_group=code,
            competition=LEAGUES.get(code, code),
            season=season,
            date=m["date"],
            home_team=canonical_team_name(team1),
            away_team=canonical_team_name(team2),
            home_score=int(ft[0]),
            away_score=int(ft[1]),
            neutral=False,
        ))
    return rows


def fetch(codes: list[str] | None = None) -> list[MatchRow]:
    rows: list[MatchRow] = []
    session = make_session()
    for code in codes or list(LEAGUES):
        for season in seasons():
            url = f"{BASE_URL}/{season}/{code}.json"
            resp = session.get(url, timeout=60)
            if resp.status_code == 404:  # season not published for this league
                continue
            resp.raise_for_status()
            rows.extend(parse_season_json(resp.json(), code, season))
    return rows
