"""ETL entry point.

    python -m app.etl.cli refresh          # download everything, rebuild models
    python -m app.etl.cli refresh --only international|leagues
"""
import argparse
import sys
import time

from ..analytics import backtest, dixon_coles, elo, ml
from ..db import get_conn
from . import base, international, leagues

SOURCES = {
    "international": (international.SOURCE, international.fetch),
    "leagues": (leagues.SOURCE, leagues.fetch),
}


def refresh(only: str | None = None) -> None:
    conn = get_conn()
    for name, (source, fetch) in SOURCES.items():
        if only and only != name:
            continue
        t0 = time.time()
        print(f"[{name}] downloading…", flush=True)
        rows = fetch()
        n = base.replace_source(conn, source, rows)
        print(f"[{name}] loaded {n} matches in {time.time() - t0:.1f}s")

    print("[elo] rebuilding ratings…", flush=True)
    groups = sorted(elo.rebuild_all(conn))
    print(f"[elo] done for groups: {', '.join(groups)}")

    for g in groups:
        t0 = time.time()
        params = dixon_coles.fit_group(conn, g)
        if params:
            dixon_coles.save_params(conn, g, params)
            print(f"[dixon-coles] {g}: home_adv={params['home_adv']:.3f} "
                  f"rho={params['rho']:.2f} ({time.time() - t0:.1f}s)")

        t0 = time.time()
        X, y, _, _, serving = ml.build_dataset(conn, g)
        ml.save_serving_state(conn, g, serving)
        if len(X) >= 500:
            model = ml.train(X, y)
            ml.save_model(model, g)
            print(f"[ml] {g}: trained on {len(X)} matches ({time.time() - t0:.1f}s)")

    print("[backtest] evaluating models (walk-forward, last 2 years)…", flush=True)
    for res in backtest.run_all(conn):
        print(f"[backtest] {res['rating_group']:14s} {res['model']:12s} "
              f"acc={res['accuracy']:.3f} brier={res['brier']:.3f} "
              f"(home-baseline acc={res['baseline_home_accuracy']:.3f}) "
              f"n={res['n_matches']}")
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.etl.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("refresh", help="download data and rebuild models")
    p.add_argument("--only", choices=list(SOURCES), default=None)
    args = parser.parse_args()
    if args.cmd == "refresh":
        refresh(only=args.only)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
