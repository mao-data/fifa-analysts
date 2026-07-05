"""Historical bookmaker odds from football-data.co.uk (free CSVs, top-5
leagues since 2010-11, updated twice weekly).

NOTE: football-data.co.uk is blocked by this sandbox's network policy — run
`python -m app.etl.cli odds` from an environment with normal internet access.
The market-vs-model comparison (/api/model/market) activates automatically
once the `odds` table has rows.

Odds preference order per match: Pinnacle closing (PSC*) — the literature's
gold standard — then Pinnacle (PS*), Bet365 (B365*), market average (Avg*).
Team names use football-data's short forms ("Man United", "Ath Madrid"); we
resolve them against the teams already in our matches table via an alias map
plus fuzzy matching, and report anything unresolved rather than guessing
silently."""
import csv
import difflib
import io

import requests

from .base import canonical_team_name

BASE_URL = "https://www.football-data.co.uk/mmz4281"
DIVISIONS = {"E0": "en.1", "SP1": "es.1", "D1": "de.1", "I1": "it.1", "F1": "fr.1"}
FIRST_SEASON_START = 2010

BOOKS = [("PSCH", "PSCD", "PSCA", "pinnacle_closing"),
         ("PSH", "PSD", "PSA", "pinnacle"),
         ("B365H", "B365D", "B365A", "bet365"),
         ("AvgH", "AvgD", "AvgA", "average")]

ALIASES = {
    "man united": "Manchester United", "man city": "Manchester City",
    "nott'm forest": "Nottingham Forest", "sheffield utd": "Sheffield United",
    "sheffield weds": "Sheffield Wednesday", "wolves": "Wolverhampton Wanderers",
    "west brom": "West Bromwich Albion", "qpr": "Queens Park Rangers",
    "spurs": "Tottenham Hotspur", "newcastle": "Newcastle United",
    "ath madrid": "Atlético Madrid", "ath bilbao": "Athletic Bilbao",
    "espanol": "Espanyol", "sociedad": "Real Sociedad", "betis": "Real Betis",
    "celta": "Celta de Vigo", "vallecano": "Rayo Vallecano",
    "la coruna": "Deportivo La Coruña", "m'gladbach": "Borussia Mönchengladbach",
    "ein frankfurt": "Eintracht Frankfurt", "fc koln": "Köln",
    "bayern munich": "Bayern München", "paris sg": "Paris Saint-Germain",
    "st etienne": "Saint-Étienne", "inter": "Internazionale",
}


def seasons(first: int = FIRST_SEASON_START, last: int | None = None) -> list[str]:
    import datetime as dt
    today = dt.date.today()
    last = last or (today.year if today.month >= 8 else today.year - 1)
    return [f"{str(y)[-2:]}{str(y + 1)[-2:]}" for y in range(first, last + 1)]


class NameResolver:
    def __init__(self, known: set[str]):
        self.known = known
        self.by_canonical = {canonical_team_name(k).lower(): k for k in known}
        self.cache: dict[str, str | None] = {}

    def resolve(self, raw: str) -> str | None:
        if raw in self.cache:
            return self.cache[raw]
        low = raw.strip().lower()
        result = None
        if low in ALIASES and ALIASES[low] in self.known:
            result = ALIASES[low]
        elif low in self.by_canonical:
            result = self.by_canonical[low]
        else:
            close = difflib.get_close_matches(low, list(self.by_canonical), n=1, cutoff=0.8)
            if close:
                result = self.by_canonical[close[0]]
        self.cache[raw] = result
        return result


def _iso_date(d: str) -> str | None:
    parts = d.strip().split("/")
    if len(parts) != 3:
        return None
    day, month, year = parts
    if len(year) == 2:
        year = ("20" if int(year) < 80 else "19") + year
    return f"{year}-{int(month):02d}-{int(day):02d}"


def parse_csv(text: str, group: str, resolver: NameResolver) -> tuple[list[tuple], set[str]]:
    rows, unresolved = [], set()
    for rec in csv.DictReader(io.StringIO(text)):
        date = _iso_date(rec.get("Date", ""))
        if not date or not rec.get("HomeTeam"):
            continue
        home = resolver.resolve(rec["HomeTeam"])
        away = resolver.resolve(rec["AwayTeam"])
        if not home or not away:
            unresolved.update(n for n, r in
                              ((rec["HomeTeam"], home), (rec["AwayTeam"], away)) if not r)
            continue
        for oh_k, od_k, oa_k, book in BOOKS:
            try:
                oh, od, oa = float(rec[oh_k]), float(rec[od_k]), float(rec[oa_k])
            except (KeyError, TypeError, ValueError):
                continue
            if min(oh, od, oa) > 1.0:
                rows.append((group, date, home, away, book, oh, od, oa))
                break
    return rows, unresolved


def known_teams(conn, group: str) -> set[str]:
    return {r["t"] for r in conn.execute(
        "SELECT DISTINCT home_team AS t FROM matches WHERE rating_group = ? "
        "UNION SELECT DISTINCT away_team FROM matches WHERE rating_group = ?",
        (group, group))}


def refresh(conn, progress=print) -> int:
    session = requests.Session()
    total = 0
    with conn:
        conn.execute("DELETE FROM odds")
    for div, group in DIVISIONS.items():
        resolver = NameResolver(known_teams(conn, group))
        rows: list[tuple] = []
        unresolved: set[str] = set()
        for season in seasons():
            resp = session.get(f"{BASE_URL}/{season}/{div}.csv", timeout=60)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            parsed, missing = parse_csv(resp.text, group, resolver)
            rows.extend(parsed)
            unresolved |= missing
        with conn:
            conn.executemany("INSERT OR REPLACE INTO odds VALUES (?,?,?,?,?,?,?,?)", rows)
        progress(f"[odds] {group}: {len(rows)} matches"
                 + (f" (unresolved names: {sorted(unresolved)})" if unresolved else ""))
        total += len(rows)
    return total
