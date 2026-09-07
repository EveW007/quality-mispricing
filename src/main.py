from __future__ import annotations

import argparse
import json
import sys

try:
    from .pipeline import run_daily_pipeline
    from .settings import load_settings
    from .storage import SnapshotStore
except ImportError:
    from pipeline import run_daily_pipeline
    from settings import load_settings
    from storage import SnapshotStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Quality Mispricing daily research pipeline."
    )
    parser.add_argument("--config", default="config.json", help="Path to config JSON")
    parser.add_argument(
        "--offline", action="store_true", help="Use cached data only; never access the network"
    )
    parser.add_argument(
        "--skip-sec", action="store_true", help="Skip SEC primary-source verification"
    )
    parser.add_argument(
        "--status", action="store_true", help="Show recent pipeline run status and exit"
    )
    parser.add_argument(
        "--print-json", action="store_true", help="Print the complete output bundle"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        settings = load_settings(args.config)
        if args.status:
            print(json.dumps(SnapshotStore(settings.database_path).run_history(), indent=2))
            return 0
        bundle = run_daily_pipeline(settings, args.offline, args.skip_sec)
    except Exception as exc:
        print(f"pipeline failed: {exc}", file=sys.stderr)
        return 1
    if args.print_json:
        print(json.dumps(bundle, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"report: {bundle['report_paths']['markdown']}")
        print(f"data:   {bundle['report_paths']['json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
