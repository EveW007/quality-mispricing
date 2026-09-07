#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.pipeline import run_daily_pipeline
from src.settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Locked daily Quality Mispricing runner")
    parser.add_argument("--config", default=str(PROJECT_DIR / "config.json"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--skip-sec", action="store_true")
    return parser


def _logger(reports_dir: Path) -> logging.Logger:
    reports_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("quality_mispricing_daily")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(
        reports_dir / f"runner-{datetime.now():%Y%m%d}.log", encoding="utf-8"
    )
    stream_handler = logging.StreamHandler()
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(args.config)
    lock_path = settings.data_dir / "daily-runner.lock"
    with lock_path.open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("daily pipeline is already running; skipped duplicate invocation")
            return 0
        logger = _logger(settings.reports_dir)
        logger.info("run started; offline=%s skip_sec=%s", args.offline, args.skip_sec)
        try:
            bundle = run_daily_pipeline(settings, args.offline, args.skip_sec)
        except Exception:
            logger.exception("run failed")
            return 1
        logger.info("run succeeded; report=%s", bundle["report_paths"]["markdown"])
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
