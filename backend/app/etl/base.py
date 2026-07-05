"""Shared ETL types and helpers. Data sources are pluggable: implement
`fetch() -> list[MatchRow]` and register in cli.py to add a new source
(e.g. a live API once deployed outside the sandbox)."""
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def make_session(retries: int = 3) -> requests.Session:
    """HTTP session with retry/backoff so a transient blip doesn't kill a
    multi-minute refresh. Retries connection errors and 5xx/429 responses."""
    session = requests.Session()
    retry = Retry(total=retries, backoff_factor=1.5,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

# Common club-name prefixes/suffixes that vary across seasons in the
# openfootball data ("Tottenham Hotspur" vs "Tottenham Hotspur FC").
# Stripping them gives one canonical name per club so Elo history and
# stats stay continuous across seasons.
_PREFIXES = (
    "1. FC ", "1. FSV ", "FC ", "AFC ", "AC ", "ACF ", "AS ", "SS ", "SSC ",
    "US ", "RC ", "RCD ", "CA ", "CD ", "SD ", "UD ", "CF ", "SC ", "SV ",
    "OGC ", "LOSC ", "ES ", "SM ",
)
_SUFFIXES = (
    " FC", " AFC", " CF", " CD", " UD", " AC", " SC", " BC", " 1846", " 05",
    " 04", " 1899", " 1909", " 98", " 03", " 96", " 09",
)


def canonical_team_name(name: str) -> str:
    name = " ".join(name.split())
    changed = True
    while changed:
        changed = False
        for p in _PREFIXES:
            if name.startswith(p) and len(name) > len(p) + 2:
                name = name[len(p):]
                changed = True
        for s in _SUFFIXES:
            if name.endswith(s) and len(name) > len(s) + 2:
                name = name[: -len(s)]
                changed = True
    return name.strip()


@dataclass
class MatchRow:
    source: str
    scope: str          # 'international' | 'league'
    rating_group: str   # 'international' or league code e.g. 'en.1'
    competition: str
    season: str | None
    date: str           # ISO yyyy-mm-dd
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    neutral: bool = False


def replace_source(conn, source: str, rows: list[MatchRow]) -> int:
    """Replace all matches of one source atomically."""
    with conn:
        conn.execute("DELETE FROM matches WHERE source = ?", (source,))
        conn.executemany(
            """INSERT INTO matches (source, scope, rating_group, competition,
                   season, date, home_team, away_team, home_score, away_score, neutral)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            [(r.source, r.scope, r.rating_group, r.competition, r.season, r.date,
              r.home_team, r.away_team, r.home_score, r.away_score, int(r.neutral))
             for r in rows],
        )
    return len(rows)
