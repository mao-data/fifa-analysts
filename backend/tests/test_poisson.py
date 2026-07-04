from math import exp

from app.analytics import poisson
from tests.conftest import load, make_match


def test_pmf_matches_formula():
    assert abs(poisson.poisson_pmf(1.5, 0) - exp(-1.5)) < 1e-12
    assert abs(poisson.poisson_pmf(2.0, 2) - exp(-2.0) * 2.0) < 1e-12


def test_outcome_probs_sum_to_one():
    m = poisson.score_matrix(1.6, 1.1)
    w, d, l = poisson.outcome_probs(m)
    assert abs(w + d + l - 1.0) < 1e-9
    assert w > l  # higher lambda should favour the home side


def test_equal_lambdas_symmetric():
    w, d, l = poisson.outcome_probs(poisson.score_matrix(1.3, 1.3))
    assert abs(w - l) < 1e-9
    assert d > 0.2  # equal sides draw often


def test_estimate_lambdas_stronger_attack(conn):
    rows = []
    # A scores heavily against everyone; B concedes heavily.
    for i in range(10):
        rows.append(make_match("A", "C", 3, 0, date=f"2024-02-{i+1:02d}"))
        rows.append(make_match("B", "C", 0, 2, date=f"2024-03-{i+1:02d}"))
    load(conn, rows)
    lam = poisson.estimate_lambdas(conn, "en.1", "A", "B")
    assert lam is not None
    lam_home, lam_away = lam
    assert lam_home > lam_away


def test_estimate_lambdas_unknown_team(conn):
    load(conn, [make_match("A", "B", 1, 0)])
    assert poisson.estimate_lambdas(conn, "en.1", "A", "Nowhere") is None
