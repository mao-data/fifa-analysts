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
    rating_group TEXT PRIMARY KEY,
    test_from    TEXT NOT NULL,
    n_matches    INTEGER NOT NULL,
    accuracy     REAL NOT NULL,
    brier        REAL NOT NULL,
    baseline_home_accuracy REAL NOT NULL,
    baseline_brier REAL NOT NULL,
    draw_rate    REAL NOT NULL
);
"""


def get_conn(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: FastAPI may open and close a request's
    # connection on different threadpool threads; each request gets its own
    # connection, so cross-thread sharing never actually happens.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn
