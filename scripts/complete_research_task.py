#!/usr/bin/env python3
"""Mark a manually generated, source-cited research report as completed."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from src.settings import load_settings
from src.storage import SnapshotStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Complete an AI Berkshire research task")
    parser.add_argument("task_id")
    parser.add_argument("report_path", help="Existing Markdown report path")
    parser.add_argument("--config", default=str(PROJECT_DIR / "config.json"))
    args = parser.parse_args()
    report = Path(args.report_path).expanduser().resolve()
    if not report.is_file():
        parser.error(f"report does not exist: {report}")
    settings = load_settings(args.config)
    SnapshotStore(settings.database_path).complete_research_task(args.task_id, str(report))
    print(f"completed {args.task_id}: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
