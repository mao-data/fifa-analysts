"""ETL entry point.

    python -m app.etl.cli refresh          # match data + goalscorers, rebuild models
    python -m app.etl.cli refresh --only international|leagues
    python -m app.etl.cli statsbomb        # xG shot data (WC 2022, Euro 2024, Copa 2024)
    python -m app.etl.cli transfermarkt    # squad market values (needs open internet)
"""
import argparse
import sys
import time

from ..analytics import backtest, dixon_coles, elo, ml
from ..db import get_conn
from . import base, international, leagues, scorers, statsbomb, transfermarkt

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

    if only in (None, "international"):
        t0 = time.time()
        n = scorers.replace(conn, scorers.fetch())
        print(f"[scorers] loaded {n} goals in {time.time() - t0:.1f}s")

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
    p = sub.add_parser("refresh", help="download match data and rebuild models")
    p.add_argument("--only", choices=list(SOURCES), default=None)
    sub.add_parser("statsbomb", help="download StatsBomb xG shot data (~150 matches)")
    sub.add_parser("transfermarkt",
                   help="download squad market values (blocked in the sandbox; "
                        "run from an environment with open internet)")
    args = parser.parse_args()
    if args.cmd == "refresh":
        refresh(only=args.only)
    elif args.cmd == "statsbomb":
        conn = get_conn()
        statsbomb.refresh(conn)
        conn.close()
    elif args.cmd == "transfermarkt":
        conn = get_conn()
        try:
            transfermarkt.refresh(conn)
        except Exception as e:  # noqa: BLE001 - surface a helpful hint
            print(f"[transfermarkt] download failed: {e}\n"
                  "This endpoint is blocked inside the Claude sandbox. Run this "
                  "command from your own machine, then re-run "
                  "'python -m app.etl.cli refresh' to retrain the model with "
                  "the market-value feature.")
            sys.exit(1)
        print("[transfermarkt] now re-run 'refresh' to retrain models with the "
              "market-value feature.")
        conn.close()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
