"""StatsBomb open-data (github.com/statsbomb/open-data, free for research use).

Full event files run to several MB per match, so this ETL is a separate
command (`python -m app.etl.cli statsbomb`), downloads one tournament at a
time, and keeps only what the site needs: the match list and every shot
(location, xG, outcome). ~50 shots per match instead of ~3,500 events.
"""
import requests

BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

# (competition_name, season_name) pairs to ingest; resolved to IDs at runtime
# so upstream ID changes can't break us silently.
TOURNAMENTS = [
    ("FIFA World Cup", "2022"),
    ("UEFA Euro", "2024"),
    ("Copa America", "2024"),
]


def _get(session: requests.Session, path: str):
    resp = session.get(f"{BASE}/{path}", timeout=120)
    resp.raise_for_status()
    return resp.json()


def resolve_ids(session: requests.Session) -> list[tuple[int, int, str, str]]:
    comps = _get(session, "competitions.json")
    out = []
    for name, season in TOURNAMENTS:
        for c in comps:
            if c["competition_name"] == name and c["season_name"] == season:
                out.append((c["competition_id"], c["season_id"], name, season))
                break
    return out


def parse_match(m: dict, comp: str, season: str) -> tuple:
    return (
        m["match_id"], comp, season, m["match_date"],
        (m.get("competition_stage") or {}).get("name"),
        m["home_team"]["home_team_name"], m["away_team"]["away_team_name"],
        m["home_score"], m["away_score"],
        (m.get("stadium") or {}).get("name"),
    )


def parse_shots(events: list[dict], match_id: int) -> list[tuple]:
    shots = []
    for e in events:
        if (e.get("type") or {}).get("name") != "Shot":
            continue
        if e.get("period") == 5:  # penalty shootout, not open play
            continue
        shot = e.get("shot") or {}
        loc = e.get("location") or [None, None]
        if shot.get("statsbomb_xg") is None or loc[0] is None:
            continue
        shots.append((
            match_id,
            (e.get("team") or {}).get("name", ""),
            (e.get("player") or {}).get("name", ""),
            e.get("minute", 0),
            loc[0], loc[1],
            shot["statsbomb_xg"],
            (shot.get("outcome") or {}).get("name", ""),
            (shot.get("body_part") or {}).get("name"),
            (shot.get("type") or {}).get("name"),
        ))
    return shots


def refresh(conn, progress=print) -> int:
    session = requests.Session()
    total_shots = 0
    for comp_id, season_id, comp, season in resolve_ids(session):
        matches = _get(session, f"matches/{comp_id}/{season_id}.json")
        progress(f"[statsbomb] {comp} {season}: {len(matches)} matches")
        match_rows = [parse_match(m, comp, season) for m in matches]
        shot_rows: list[tuple] = []
        for i, m in enumerate(matches, 1):
            events = _get(session, f"events/{m['match_id']}.json")
            shot_rows.extend(parse_shots(events, m["match_id"]))
            if i % 16 == 0:
                progress(f"[statsbomb]   …{i}/{len(matches)} matches downloaded")
        with conn:
            conn.execute("DELETE FROM sb_shots WHERE match_id IN "
                         "(SELECT match_id FROM sb_matches WHERE competition = ? AND season = ?)",
                         (comp, season))
            conn.execute("DELETE FROM sb_matches WHERE competition = ? AND season = ?",
                         (comp, season))
            conn.executemany(
                "INSERT INTO sb_matches VALUES (?,?,?,?,?,?,?,?,?,?)", match_rows)
            conn.executemany(
                "INSERT INTO sb_shots VALUES (?,?,?,?,?,?,?,?,?,?)", shot_rows)
        progress(f"[statsbomb] {comp} {season}: stored {len(shot_rows)} shots")
        total_shots += len(shot_rows)
    return total_shots
