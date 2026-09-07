#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from src.settings import load_settings
from src.storage import SnapshotStore
from src.research_queue import render_research_brief


def main() -> int:
    parser = argparse.ArgumentParser(description="Show pending AI Berkshire research tasks")
    parser.add_argument("--config", default=str(PROJECT_DIR / "config.json"))
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    settings = load_settings(args.config)
    tasks = SnapshotStore(settings.database_path).pending_research_tasks(args.limit)
    if args.format == "markdown":
        print("\n---\n".join(render_research_brief(task) for task in tasks))
    else:
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
