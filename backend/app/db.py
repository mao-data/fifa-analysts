"""SQLite storage for match data and precomputed model outputs."""
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "football.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,            -- 'international' | 'openfootball'
    scope       TEXT NOT NULL,            -- 'international' | 'league'
    rating_group TEXT NOT NULL,           -- 'international' or league code e.g. 'en.1'
    competition TEXT NOT NULL,            -- tournament name or league display name
    season      TEXT,                     -- '2024-25' for leagues, NULL for international
    date        TEXT NOT NULL,            -- ISO yyyy-mm-dd
    home_team   TEXT NOT NULL,
    away_team   TEXT NOT NULL,
    home_score  INTEGER NOT NULL,
    away_score  INTEGER NOT NULL,
    neutral     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_matches_group_date ON matches(rating_group, date);
CREATE INDEX IF NOT EXISTS idx_matches_home ON matches(rating_group, home_team);
CREATE INDEX IF NOT EXISTS idx_matches_away ON matches(rating_group, away_team);
CREATE INDEX IF NOT EXISTS idx_matches_season ON matches(rating_group, season);

CREATE TABLE IF NOT EXISTS elo_history (
    match_id    INTEGER NOT NULL REFERENCES matches(id),
    rating_group TEXT NOT NULL,
    date        TEXT NOT NULL,
    team        TEXT NOT NULL,
    elo_before  REAL NOT NULL,
    elo_after   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_elo_history_team ON elo_history(rating_group, team, date);

CREATE TABLE IF NOT EXISTS elo_ratings (
    rating_group TEXT NOT NULL,
    team        TEXT NOT NULL,
    rating      REAL NOT NULL,
    matches     INTEGER NOT NULL,
    last_date   TEXT NOT NULL,
    PRIMARY KEY (rating_group, team)
);

CREATE TABLE IF NOT EXISTS backtest_results (
    rating_group TEXT NOT NULL,
    model        TEXT NOT NULL,            -- 'elo' | 'dixon_coles' | 'ml' | 'ensemble'
    test_from    TEXT NOT NULL,
    n_matches    INTEGER NOT NULL,
    accuracy     REAL NOT NULL,
    brier        REAL NOT NULL,
    baseline_home_accuracy REAL NOT NULL,
    baseline_brier REAL NOT NULL,
    draw_rate    REAL NOT NULL,
    PRIMARY KEY (rating_group, model)
);

CREATE TABLE IF NOT EXISTS dc_params (
    rating_group TEXT PRIMARY KEY,
    params       TEXT NOT NULL             -- JSON: attack/defence/home_adv/rho
);

CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    home_team   TEXT NOT NULL,
    away_team   TEXT NOT NULL,
    team        TEXT NOT NULL,             -- the scoring team
    scorer      TEXT NOT NULL,
    minute      INTEGER,
    own_goal    INTEGER NOT NULL DEFAULT 0,
    penalty     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_goals_team ON goals(team);
CREATE INDEX IF NOT EXISTS idx_goals_scorer ON goals(scorer);

CREATE TABLE IF NOT EXISTS sb_matches (
    match_id    INTEGER PRIMARY KEY,
    competition TEXT NOT NULL,
    season      TEXT NOT NULL,
    date        TEXT NOT NULL,
    stage       TEXT,
    home_team   TEXT NOT NULL,
    away_team   TEXT NOT NULL,
    home_score  INTEGER NOT NULL,
    away_score  INTEGER NOT NULL,
    stadium     TEXT
);

CREATE TABLE IF NOT EXISTS sb_shots (
    match_id    INTEGER NOT NULL REFERENCES sb_matches(match_id),
    team        TEXT NOT NULL,
    player      TEXT NOT NULL,
    minute      INTEGER NOT NULL,
    x           REAL NOT NULL,             -- StatsBomb pitch coords (120 x 80)
    y           REAL NOT NULL,
    xg          REAL NOT NULL,
    outcome     TEXT NOT NULL,             -- 'Goal', 'Saved', 'Off T', …
    body_part   TEXT,
    play_type   TEXT                       -- 'Open Play', 'Penalty', …
);
CREATE INDEX IF NOT EXISTS idx_sb_shots_match ON sb_shots(match_id);

CREATE TABLE IF NOT EXISTS market_values (
    rating_group TEXT NOT NULL,
    team        TEXT NOT NULL,             -- canonical name matching matches table
    date        TEXT NOT NULL,             -- valuation snapshot date
    squad_value REAL NOT NULL,             -- total squad market value, EUR
    PRIMARY KEY (rating_group, team, date)
);

CREATE TABLE IF NOT EXISTS ml_team_state (
    rating_group TEXT NOT NULL,
    team        TEXT NOT NULL,
    elo         REAL NOT NULL,
    form5       REAL,
    gf10        REAL,
    ga10        REAL,
    last_date   TEXT,
    n           INTEGER NOT NULL,
    PRIMARY KEY (rating_group, team)
);
"""

SCHEMA_VERSION = 2


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 2:
        # v1 backtest_results had no 'model' column; contents are rebuilt by
        # the ETL, so dropping is safe.
        conn.execute("DROP TABLE IF EXISTS backtest_results")
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def get_conn(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI may open and close a request's
    # connection on different threadpool threads; each request gets its own
    # connection, so cross-thread sharing never actually happens.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    _migrate(conn)
    conn.executescript(SCHEMA)
    return conn
