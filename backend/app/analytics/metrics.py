"""Shared forecast-evaluation helpers (used by backtest, tournament reports
and the market comparison — keep the definitions in one place so every
surface scores models identically)."""


def brier(probs, outcome: int) -> float:
    """Multiclass Brier score for one match: 0 perfect, 2 worst."""
    return sum((p - (1.0 if k == outcome else 0.0)) ** 2 for k, p in enumerate(probs))


def pick(probs) -> int:
    """Index of the most likely outcome (0 home win / 1 draw / 2 away win)."""
    return max(range(3), key=lambda k: probs[k])
