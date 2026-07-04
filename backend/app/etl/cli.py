"""ETL entry point.

    python -m app.etl.cli refresh          # download everything, rebuild models
    python -m app.etl.cli refresh --only international|leagues
"""
import argparse
import sys
import time

from ..analytics import backtest, elo
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
    groups = elo.rebuild_all(conn)
    print(f"[elo] done for groups: {', '.join(sorted(groups))}")

    print("[backtest] evaluating model…", flush=True)
    for res in backtest.run_all(conn):
        print(f"[backtest] {res['rating_group']}: acc={res['accuracy']:.3f} "
              f"(baseline {res['baseline_home_accuracy']:.3f}), "
              f"brier={res['brier']:.3f} (baseline {res['baseline_brier']:.3f}), "
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
