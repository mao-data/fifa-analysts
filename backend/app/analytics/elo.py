"""Elo rating engine, following the World Football Elo Ratings conventions
(eloratings.net): K weighted by match importance, home advantage skipped on
neutral ground, and a margin-of-victory multiplier."""
from collections import defaultdict

BASE_ELO = 1500.0
HOME_ADV_INTL = 100.0
HOME_ADV_LEAGUE = 60.0
K_LEAGUE = 20.0

_CONTINENTAL_FINALS = (
    "uefa euro", "copa américa", "copa america", "african cup of nations",
    "africa cup of nations", "afc asian cup", "gold cup", "oceania nations cup",
    "confederations cup", "concacaf championship",
)


def k_for_international(tournament: str) -> float:
    t = tournament.lower()
    if "qualification" in t or "qualifier" in t:
        return 40.0
    if t == "fifa world cup":
        return 60.0
    if any(name in t for name in _CONTINENTAL_FINALS):
        return 50.0
    if "nations league" in t:
        return 40.0
    if "friendly" in t:
        return 20.0
    return 30.0


def expected_score(rating_diff: float) -> float:
    """Expected score (win prob + half draw prob) for the higher-rated side."""
    return 1.0 / (1.0 + 10.0 ** (-rating_diff / 400.0))


def mov_multiplier(goal_diff: int) -> float:
    d = abs(goal_diff)
    if d <= 1:
        return 1.0
    if d == 2:
        return 1.5
    return 1.75 + (d - 3) / 8.0


def rating_diff(home_elo: float, away_elo: float, neutral: bool, home_adv: float) -> float:
    return home_elo - away_elo + (0.0 if neutral else home_adv)


def update(home_elo: float, away_elo: float, home_score: int, away_score: int,
           neutral: bool, k: float, home_adv: float) -> tuple[float, float]:
    """Return (new_home_elo, new_away_elo) after one match."""
    e_home = expected_score(rating_diff(home_elo, away_elo, neutral, home_adv))
    if home_score > away_score:
        s_home = 1.0
    elif home_score == away_score:
        s_home = 0.5
    else:
        s_home = 0.0
    delta = k * mov_multiplier(home_score - away_score) * (s_home - e_home)
    return home_elo + delta, away_elo - delta


def iter_group_matches(conn, group: str):
    return conn.execute(
        """SELECT id, date, home_team, away_team, home_score, away_score,
                  neutral, competition
           FROM matches WHERE rating_group = ? ORDER BY date, id""",
        (group,),
    )


def rebuild_group(conn, group: str) -> dict[str, float]:
    """Replay all matches of a group chronologically; persist per-match
    snapshots (for trend charts) and final ratings. Returns final ratings."""
    is_intl = group == "international"
    home_adv = HOME_ADV_INTL if is_intl else HOME_ADV_LEAGUE
    ratings: dict[str, float] = defaultdict(lambda: BASE_ELO)
    played: dict[str, int] = defaultdict(int)
    last_date: dict[str, str] = {}
    history: list[tuple] = []

    for m in iter_group_matches(conn, group).fetchall():
        h, a = m["home_team"], m["away_team"]
        k = k_for_international(m["competition"]) if is_intl else K_LEAGUE
        old_h, old_a = ratings[h], ratings[a]
        new_h, new_a = update(old_h, old_a, m["home_score"], m["away_score"],
                              bool(m["neutral"]), k, home_adv)
        ratings[h], ratings[a] = new_h, new_a
        played[h] += 1
        played[a] += 1
        last_date[h] = last_date[a] = m["date"]
        history.append((m["id"], group, m["date"], h, old_h, new_h))
        history.append((m["id"], group, m["date"], a, old_a, new_a))

    with conn:
        conn.execute("DELETE FROM elo_history WHERE rating_group = ?", (group,))
        conn.execute("DELETE FROM elo_ratings WHERE rating_group = ?", (group,))
        conn.executemany(
            "INSERT INTO elo_history (match_id, rating_group, date, team, elo_before, elo_after)"
            " VALUES (?,?,?,?,?,?)", history)
        conn.executemany(
            "INSERT INTO elo_ratings (rating_group, team, rating, matches, last_date)"
            " VALUES (?,?,?,?,?)",
            [(group, t, r, played[t], last_date[t]) for t, r in ratings.items()])
    return dict(ratings)


def rebuild_all(conn) -> list[str]:
    groups = [r["rating_group"] for r in
              conn.execute("SELECT DISTINCT rating_group FROM matches")]
    for g in groups:
        rebuild_group(conn, g)
    return groups
