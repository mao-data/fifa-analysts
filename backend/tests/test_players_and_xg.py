from app.analytics import players, xg
from app.etl import scorers, statsbomb


GOALS_CSV = """date,home_team,away_team,team,scorer,minute,own_goal,penalty
2022-12-18,Argentina,France,Argentina,Lionel Messi,23,FALSE,TRUE
2022-12-18,Argentina,France,Argentina,Lionel Messi,108,FALSE,FALSE
2022-12-18,Argentina,France,France,Kylian Mbappé,80,FALSE,TRUE
2022-12-18,Argentina,France,France,Kylian Mbappé,81,FALSE,FALSE
2022-12-18,Argentina,France,France,Kylian Mbappé,118,FALSE,TRUE
2022-12-13,Argentina,Croatia,Argentina,Lionel Messi,34,FALSE,TRUE
2021-06-11,Turkey,Italy,Italy,Merih Demiral,53,TRUE,FALSE
2026-01-01,X,Y,X,NA,NA,FALSE,FALSE
"""


def _load_goals(conn):
    scorers.replace(conn, scorers.parse_csv(GOALS_CSV))


def test_scorers_parse_skips_na_and_flags():
    rows = scorers.parse_csv(GOALS_CSV)
    assert len(rows) == 7  # NA scorer dropped
    own = [r for r in rows if r[6] == 1]
    assert len(own) == 1 and own[0][4] == "Merih Demiral"


def test_top_scorers_excludes_own_goals(conn):
    _load_goals(conn)
    top = players.top_scorers(conn)
    assert top[0]["scorer"] in ("Lionel Messi", "Kylian Mbappé")
    assert all(t["scorer"] != "Merih Demiral" for t in top)
    messi = next(t for t in top if t["scorer"] == "Lionel Messi")
    assert messi["goals"] == 3 and messi["penalties"] == 2


def test_player_profile_minutes(conn):
    _load_goals(conn)
    p = players.player_profile(conn, "Kylian Mbappé")
    assert p["goals"] == 3
    # 80', 81', 118' all fold into the 76-90+ bucket.
    last = next(b for b in p["minute_distribution"] if b["period"] == "76-90+")
    assert last["goals"] == 3
    assert players.player_profile(conn, "Nobody") is None


def test_team_scoring_concentration(conn):
    _load_goals(conn)
    t = players.team_scoring(conn, "Argentina")
    assert t["total_goals"] == 3
    assert t["top_scorer_share"] == 1.0  # all by Messi
    assert t["concentration_hhi"] == 1.0


SB_EVENTS = [
    {"type": {"name": "Pass"}, "team": {"name": "A"}},
    {"type": {"name": "Shot"}, "team": {"name": "A"}, "player": {"name": "P1"},
     "minute": 10, "location": [110.0, 40.0],
     "shot": {"statsbomb_xg": 0.8, "outcome": {"name": "Goal"},
              "body_part": {"name": "Right Foot"}, "type": {"name": "Open Play"}}},
    {"type": {"name": "Shot"}, "team": {"name": "B"}, "player": {"name": "P2"},
     "minute": 50, "location": [100.0, 30.0],
     "shot": {"statsbomb_xg": 0.1, "outcome": {"name": "Saved"},
              "body_part": {"name": "Head"}, "type": {"name": "Open Play"}}},
    {"type": {"name": "Shot"}, "team": {"name": "B"}, "player": {"name": "P2"},
     "minute": 60, "location": None,  # malformed -> skipped
     "shot": {"statsbomb_xg": 0.2}},
]


def test_statsbomb_parse_and_aggregate(conn):
    match = {"match_id": 1, "match_date": "2022-12-18",
             "competition_stage": {"name": "Final"},
             "home_team": {"home_team_name": "A"}, "away_team": {"away_team_name": "B"},
             "home_score": 1, "away_score": 0, "stadium": {"name": "Lusail"}}
    with conn:
        conn.execute("INSERT INTO sb_matches VALUES (?,?,?,?,?,?,?,?,?,?)",
                     statsbomb.parse_match(match, "FIFA World Cup", "2022"))
        conn.executemany("INSERT INTO sb_shots VALUES (?,?,?,?,?,?,?,?,?,?)",
                         statsbomb.parse_shots(SB_EVENTS, 1))
    teams = xg.team_table(conn, "FIFA World Cup", "2022")
    a = next(t for t in teams if t["team"] == "A")
    assert a["goals"] == 1 and a["xg_for"] == 0.8
    assert a["xg_against"] == 0.1 and a["goals_against"] == 0
    ms = xg.match_shots(conn, 1)
    assert len(ms["shots"]) == 2  # malformed shot skipped
    assert ms["xg_totals"] == {"A": 0.8, "B": 0.1}
    assert xg.match_shots(conn, 99) is None
