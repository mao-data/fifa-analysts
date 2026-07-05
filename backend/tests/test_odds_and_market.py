from app.analytics import market
from app.etl import odds
from tests.conftest import load, make_match


ODDS_CSV = """Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,B365H,B365D,B365A,PSCH,PSCD,PSCA
E0,16/08/2024,Man United,Fulham,1,0,1.60,4.20,5.50,1.62,4.30,5.60
E0,17/08/2024,Arsenal,Wolves,2,0,1.30,5.50,9.00,,,
E0,18/08/2024,Unknown XI,Fulham,0,0,2.0,3.0,4.0,2.0,3.0,4.0
E0,bad-date,Arsenal,Fulham,1,1,2.0,3.0,4.0,2.0,3.0,4.0
"""


def _resolver():
    return odds.NameResolver({
        "Manchester United", "Fulham", "Arsenal", "Wolverhampton Wanderers"})


def test_parse_csv_prefers_closing_and_resolves_names():
    rows, unresolved = odds.parse_csv(ODDS_CSV, "en.1", _resolver())
    assert len(rows) == 2
    first = rows[0]
    assert first[1] == "2024-08-16"           # dd/mm/yyyy converted
    assert first[2] == "Manchester United"    # alias resolved
    assert first[4] == "pinnacle_closing"     # PSC* preferred over B365
    assert first[5] == 1.62
    second = rows[1]
    assert second[3] == "Wolverhampton Wanderers"
    assert second[4] == "bet365"              # falls back when PSC* missing
    assert unresolved == {"Unknown XI"}


def test_resolver_fuzzy_match():
    r = _resolver()
    assert r.resolve("Wolverhampton Wanderers FC") == "Wolverhampton Wanderers"
    assert r.resolve("Completely Different") is None


def test_market_comparison(conn):
    load(conn, [make_match("A", "B", 1, 0, date="2024-01-01")])
    with conn:
        # Model said 60/25/15 (home win, correct); market said 50/30/20.
        conn.execute("INSERT INTO backtest_predictions VALUES "
                     "('en.1','2024-01-01','A','B',0.6,0.25,0.15,0)")
        # Odds with a typical ~5% margin.
        conn.execute("INSERT INTO odds VALUES "
                     "('en.1','2024-01-01','A','B','pinnacle_closing',1.9,3.3,4.8)")
        # Prediction without matching odds must be excluded from the join.
        conn.execute("INSERT INTO backtest_predictions VALUES "
                     "('en.1','2024-01-02','A','B',0.5,0.3,0.2,1)")
    res = market.compare(conn, "en.1")
    assert res["n_matches"] == 1
    assert res["model"]["accuracy"] == 1.0
    assert res["market"]["accuracy"] == 1.0
    # Margin-stripped market probs sum to 1.
    mp = res["top_divergences"][0]["market"]
    assert abs(sum(mp) - 1.0) < 0.01
    assert mp[0] > 0.5  # home favourite after stripping
    assert market.compare(conn, "de.1") is None
