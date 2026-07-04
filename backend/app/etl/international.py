"""International results from github.com/martj42/international_results (CC0).
~49,000 matches from 1872 to today, updated after every international window."""
import csv
import io

import requests

from .base import MatchRow

URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
SOURCE = "international"


def fetch(url: str = URL) -> list[MatchRow]:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return parse_csv(resp.text)


def parse_csv(text: str) -> list[MatchRow]:
    rows: list[MatchRow] = []
    for rec in csv.DictReader(io.StringIO(text)):
        # Fixtures not yet played carry NA scores — skip them.
        if rec["home_score"] in ("NA", "", None) or rec["away_score"] in ("NA", "", None):
            continue
        rows.append(MatchRow(
            source=SOURCE,
            scope="international",
            rating_group="international",
            competition=rec["tournament"],
            season=None,
            date=rec["date"],
            home_team=rec["home_team"].strip(),
            away_team=rec["away_team"].strip(),
            home_score=int(rec["home_score"]),
            away_score=int(rec["away_score"]),
            neutral=rec["neutral"].strip().upper() == "TRUE",
        ))
    return rows
