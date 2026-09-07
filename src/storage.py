from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SnapshotStore:
    """Small append-only SQLite store for runs and daily research snapshots."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    error TEXT
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    as_of TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(run_id, kind, ticker),
                    FOREIGN KEY(run_id) REFERENCES runs(run_id)
                );

                CREATE INDEX IF NOT EXISTS idx_snapshots_lookup
                    ON snapshots(kind, ticker, as_of DESC);

                CREATE TABLE IF NOT EXISTS research_tasks (
                    task_id TEXT PRIMARY KEY,
                    ticker TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source_run_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    report_path TEXT,
                    error TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_research_tasks_ticker_created
                    ON research_tasks(ticker, created_at DESC);
                """
            )

    def start_run(self) -> str:
        run_id = uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO runs(run_id, started_at, status) VALUES (?, ?, ?)",
                (run_id, utc_now().isoformat(), "RUNNING"),
            )
        return run_id

    def finish_run(self, run_id: str, status: str, error: str | None = None) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runs
                SET completed_at = ?, status = ?, error = ?
                WHERE run_id = ?
                """,
                (utc_now().isoformat(), status, error, run_id),
            )

    @contextmanager
    def run(self) -> Iterator[str]:
        run_id = self.start_run()
        try:
            yield run_id
        except Exception as exc:
            self.finish_run(run_id, "FAILED", str(exc))
            raise
        else:
            self.finish_run(run_id, "SUCCESS")

    def save_snapshot(
        self,
        run_id: str,
        kind: str,
        ticker: str,
        as_of: str,
        payload: dict[str, Any],
    ) -> None:
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO snapshots(
                    run_id, kind, ticker, as_of, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, kind, ticker) DO UPDATE SET
                    as_of = excluded.as_of,
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at
                """,
                (
                    run_id,
                    kind,
                    ticker.upper(),
                    as_of,
                    rendered,
                    utc_now().isoformat(),
                ),
            )

    def save_snapshots(
        self,
        run_id: str,
        kind: str,
        items: Iterable[tuple[str, str, dict[str, Any]]],
    ) -> None:
        rows = [
            (
                run_id,
                kind,
                ticker.upper(),
                as_of,
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                utc_now().isoformat(),
            )
            for ticker, as_of, payload in items
        ]
        if not rows:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO snapshots(
                    run_id, kind, ticker, as_of, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, kind, ticker) DO UPDATE SET
                    as_of = excluded.as_of,
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at
                """,
                rows,
            )

    def latest_snapshot(self, kind: str, ticker: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json FROM snapshots
                WHERE kind = ? AND ticker = ?
                ORDER BY as_of DESC, id DESC
                LIMIT 1
                """,
                (kind, ticker.upper()),
            ).fetchone()
        return None if row is None else json.loads(row["payload_json"])

    def run_history(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, started_at, completed_at, status, error
                FROM runs ORDER BY started_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def research_task_recently_created(self, ticker: str, cooldown_days: int) -> bool:
        cutoff = utc_now().timestamp() - cooldown_days * 24 * 60 * 60
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT created_at FROM research_tasks
                WHERE ticker = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (ticker.upper(),),
            ).fetchone()
        if row is None:
            return False
        return datetime.fromisoformat(row["created_at"]).timestamp() >= cutoff

    def create_research_task(
        self, ticker: str, source_run_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        now = utc_now().isoformat()
        task = {
            "task_id": uuid.uuid4().hex,
            "ticker": ticker.upper(),
            "created_at": now,
            "updated_at": now,
            "status": "PENDING",
            "source_run_id": source_run_id,
            "payload": payload,
            "report_path": None,
            "error": None,
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO research_tasks(
                    task_id, ticker, created_at, updated_at, status, source_run_id,
                    payload_json, report_path, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task["task_id"], task["ticker"], task["created_at"], task["updated_at"],
                    task["status"], task["source_run_id"],
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                    None, None,
                ),
            )
        return task

    def pending_research_tasks(self, limit: int = 5) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT task_id, ticker, created_at, updated_at, status, source_run_id,
                       payload_json, report_path, error
                FROM research_tasks
                WHERE status = 'PENDING'
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                **{key: row[key] for key in row.keys() if key != "payload_json"},
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def complete_research_task(self, task_id: str, report_path: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE research_tasks
                SET status = 'COMPLETED', updated_at = ?, report_path = ?, error = NULL
                WHERE task_id = ?
                """,
                (utc_now().isoformat(), report_path, task_id),
            )
