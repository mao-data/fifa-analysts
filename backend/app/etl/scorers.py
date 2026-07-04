"""International goalscorers from martj42/international_results (CC0).
One row per goal: scorer, minute, own-goal and penalty flags."""
import csv
import io

import requests

URL = "https://raw.githubusercontent.com/martj42/international_results/master/goalscorers.csv"


def fetch(url: str = URL) -> list[tuple]:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return parse_csv(resp.text)


def parse_csv(text: str) -> list[tuple]:
    rows = []
    for rec in csv.DictReader(io.StringIO(text)):
        if not rec.get("scorer") or rec["scorer"] == "NA":
            continue
        minute = rec.get("minute")
        rows.append((
            rec["date"], rec["home_team"].strip(), rec["away_team"].strip(),
            rec["team"].strip(), rec["scorer"].strip(),
            int(float(minute)) if minute and minute != "NA" else None,
            1 if rec.get("own_goal", "").upper() == "TRUE" else 0,
            1 if rec.get("penalty", "").upper() == "TRUE" else 0,
        ))
    return rows


def replace(conn, rows: list[tuple]) -> int:
    with conn:
        conn.execute("DELETE FROM goals")
        conn.executemany(
            """INSERT INTO goals (date, home_team, away_team, team, scorer,
                                  minute, own_goal, penalty)
               VALUES (?,?,?,?,?,?,?,?)""", rows)
    return len(rows)
