from app.etl.base import canonical_team_name
from app.etl.international import parse_csv
from app.etl.leagues import parse_season_json, seasons
import datetime as dt


def test_parse_csv_skips_unplayed():
    text = (
        "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral\n"
        "2022-12-18,Argentina,France,3,3,FIFA World Cup,Lusail,Qatar,TRUE\n"
        "2026-07-06,Portugal,Spain,NA,NA,FIFA World Cup,Dallas,United States,TRUE\n"
    )
    rows = parse_csv(text)
    assert len(rows) == 1
    m = rows[0]
    assert m.home_team == "Argentina" and m.neutral is True
    assert m.rating_group == "international"


def test_parse_season_json_formats():
    data = {"matches": [
        {"date": "2024-08-16", "team1": "Manchester United FC", "team2": "Fulham FC",
         "score": {"ht": [0, 0], "ft": [1, 0]}},
        {"date": "2010-08-14", "team1": "Tottenham Hotspur", "team2": "Manchester City",
         "score": {"ft": [0, 0]}},
        # Unplayed placeholder observed in 2025-26 files: score is a list.
        {"date": "2025-08-16", "team1": "Aston Villa FC", "team2": "Newcastle United FC",
         "score": [0, 0]},
        {"date": "2025-08-17", "team1": "X", "team2": "Y"},  # no score at all
    ]}
    rows = parse_season_json(data, "en.1", "2024-25")
    assert len(rows) == 2
    assert rows[0].home_team == "Manchester United"  # canonicalised
    assert rows[1].home_team == "Tottenham Hotspur"
    assert rows[0].season == "2024-25" and rows[0].rating_group == "en.1"


def test_canonical_team_name_merges_variants():
    assert canonical_team_name("Tottenham Hotspur FC") == canonical_team_name("Tottenham Hotspur")
    assert canonical_team_name("FC Barcelona") == "Barcelona"
    assert canonical_team_name("FC Bayern München") == canonical_team_name("Bayern München")
    assert canonical_team_name("AFC Bournemouth") == "Bournemouth"
    assert canonical_team_name("AS Roma") == "Roma"
    # Names that are just an affix must survive.
    assert canonical_team_name("FC") == "FC"


def test_seasons_window():
    s = seasons(dt.date(2026, 7, 4))
    assert s[0] == "2010-11"
    assert s[-1] == "2025-26"  # July → previous season is the latest
    assert seasons(dt.date(2026, 9, 1))[-1] == "2026-27"
