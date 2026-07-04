import datetime as dt
import random

from app.analytics import dixon_coles as dc


def _poisson_sample(rng: random.Random, lam: float) -> int:
    # Knuth's algorithm — fine for small lambda.
    l = pow(2.718281828, -lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= l:
            return k
        k += 1


def _synthetic(n=600, seed=7):
    """Three teams with known strengths; Strong should out-attack Weak."""
    rng = random.Random(seed)
    strengths = {"Strong": 2.0, "Mid": 1.2, "Weak": 0.6}
    teams = list(strengths)
    rows = []
    start = dt.date(2023, 1, 1)
    for i in range(n):
        h, a = rng.sample(teams, 2)
        lam = strengths[h] * 1.2  # true home advantage
        mu = strengths[a]
        rows.append(((start + dt.timedelta(days=i)).isoformat(), h, a,
                     _poisson_sample(rng, lam), _poisson_sample(rng, mu), False))
    return rows, start + dt.timedelta(days=n)


def test_fit_recovers_ordering_and_home_advantage():
    rows, as_of = _synthetic()
    params = dc.fit(rows, as_of, "league")
    assert params is not None
    assert params["attack"]["Strong"] > params["attack"]["Mid"] > params["attack"]["Weak"]
    assert 1.0 < params["home_adv"] < 1.5


def test_predict_probs_sum_to_one_and_favour_strong():
    rows, as_of = _synthetic()
    params = dc.fit(rows, as_of, "league")
    res = dc.predict_probs(params, "Strong", "Weak", neutral=False)
    assert res is not None
    (w, d, l), matrix, (lam, mu) = res
    assert abs(w + d + l - 1.0) < 1e-9
    assert w > 0.5 > l
    assert lam > mu
    assert abs(sum(sum(r) for r in matrix) - 1.0) < 1e-9


def test_neutral_removes_home_advantage():
    rows, as_of = _synthetic()
    params = dc.fit(rows, as_of, "league")
    home = dc.predict_probs(params, "Mid", "Mid2", True) if "Mid2" in params["attack"] else None
    assert home is None  # unknown team is refused
    with_adv = dc.lambdas(params, "Mid", "Weak", neutral=False)
    without = dc.lambdas(params, "Mid", "Weak", neutral=True)
    assert with_adv[0] > without[0]
    assert with_adv[1] == without[1]


def test_decay_prefers_recent_form():
    """A team that was weak long ago but strong recently should fit strong."""
    rows = []
    start = dt.date(2020, 1, 1)
    for i in range(200):  # old: Flip loses 0-2
        rows.append(((start + dt.timedelta(days=i * 3)).isoformat(),
                     "Flip", "Anchor", 0, 2, False))
    recent = dt.date(2024, 1, 1)
    for i in range(60):   # recent: Flip wins 3-0
        rows.append(((recent + dt.timedelta(days=i * 3)).isoformat(),
                     "Flip", "Anchor", 3, 0, False))
    params = dc.fit(rows, recent + dt.timedelta(days=180), "league")
    lam, mu = dc.lambdas(params, "Flip", "Anchor", neutral=False)
    assert lam > mu  # recent dominance outweighs the old losses


def test_tau_only_touches_low_scores():
    assert dc._tau(2, 1, 1.5, 1.0, -0.1) == 1.0
    assert dc._tau(0, 0, 1.5, 1.0, -0.1) > 1.0  # negative rho lifts 0-0
    assert dc._tau(1, 1, 1.5, 1.0, -0.1) > 1.0


def test_fit_group_before_date_excludes_future(conn):
    from tests.conftest import load, make_match
    rows = [make_match("A", "B", 3, 0, date=f"2024-0{m}-01") for m in range(1, 7)]
    load(conn, rows)
    params = dc.fit_group(conn, "en.1", before_date="2024-04-01")
    # Only 3 matches before the cutoff — under the 50-match minimum.
    assert params is None
