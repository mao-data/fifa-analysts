"""Squad market values from dcaribou/transfermarkt-datasets (CC0).

NOTE: the download endpoint (a public R2 bucket) is blocked by this sandbox's
network policy — run `python -m app.etl.cli transfermarkt` from an environment
with normal internet access (your laptop, your server). Everything downstream
(storage, the ML market-value feature) activates automatically once the
`market_values` table has rows; until then the feature is NaN and the model
simply ignores it.

Data model: player_valuations.csv has one row per player per revaluation
(player_id, date, market_value_in_eur, current_club_id); clubs.csv maps
club_id -> name + domestic_competition_id. We aggregate to a quarterly squad
value per club: the sum of each player's latest valuation within the quarter.
"""
import csv
import gzip
import io
import os
from collections import defaultdict

import requests

from .base import canonical_team_name

BASE_URL = os.environ.get(
    "TRANSFERMARKT_DATA_URL",
    "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/csv")

# Transfermarkt domestic competition codes -> our league rating groups.
COMPETITION_TO_GROUP = {
    "GB1": "en.1", "ES1": "es.1", "L1": "de.1", "IT1": "it.1", "FR1": "fr.1",
}


def _fetch_csv(session: requests.Session, name: str) -> list[dict]:
    resp = session.get(f"{BASE_URL}/{name}", timeout=300)
    resp.raise_for_status()
    data = resp.content
    if name.endswith(".gz") or data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"))))


def quarter_end(date: str) -> str:
    y, m = int(date[:4]), int(date[5:7])
    qm = ((m - 1) // 3 + 1) * 3
    last_day = {3: 31, 6: 30, 9: 30, 12: 31}[qm]
    return f"{y}-{qm:02d}-{last_day}"


def aggregate(valuations: list[dict], clubs: list[dict]) -> list[tuple]:
    """-> rows for market_values: (rating_group, team, date, squad_value)."""
    club_info: dict[str, tuple[str, str]] = {}
    for c in clubs:
        group = COMPETITION_TO_GROUP.get(c.get("domestic_competition_id", ""))
        if group:
            club_info[c["club_id"]] = (group, canonical_team_name(c["name"]))

    # (club, quarter) -> {player: latest (date, value) in that quarter}
    latest: dict[tuple[str, str], dict[str, tuple[str, float]]] = defaultdict(dict)
    for v in valuations:
        club_id = v.get("current_club_id", "")
        if club_id not in club_info:
            continue
        value = v.get("market_value_in_eur")
        date = v.get("date", "")
        if not value or not date:
            continue
        q = quarter_end(date)
        players = latest[(club_id, q)]
        prev = players.get(v["player_id"])
        if prev is None or date > prev[0]:
            players[v["player_id"]] = (date, float(value))

    rows = []
    for (club_id, q), players in latest.items():
        group, team = club_info[club_id]
        rows.append((group, team, q, sum(val for _, val in players.values())))
    return rows


def replace(conn, rows: list[tuple]) -> int:
    with conn:
        conn.execute("DELETE FROM market_values")
        conn.executemany(
            "INSERT OR REPLACE INTO market_values VALUES (?,?,?,?)", rows)
    return len(rows)


def refresh(conn, progress=print) -> int:
    session = requests.Session()
    progress("[transfermarkt] downloading clubs.csv…")
    clubs = _fetch_csv(session, "clubs.csv")
    progress("[transfermarkt] downloading player_valuations.csv (large)…")
    valuations = _fetch_csv(session, "player_valuations.csv")
    rows = aggregate(valuations, clubs)
    n = replace(conn, rows)
    progress(f"[transfermarkt] stored {n} quarterly squad values "
             f"({len({r[1] for r in rows})} clubs)")
    return n
