import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

from storage import SnapshotStore


def test_snapshot_store_records_success_and_latest(tmp_path):
    store = SnapshotStore(tmp_path / "snapshots.sqlite3")
    with store.run() as run_id:
        store.save_snapshot(run_id, "market", "MSFT", "2026-08-11", {"price": 500})
    assert store.latest_snapshot("market", "msft") == {"price": 500}
    assert store.run_history()[0]["status"] == "SUCCESS"


def test_snapshot_store_batches_rows(tmp_path):
    store = SnapshotStore(tmp_path / "snapshots.sqlite3")
    with store.run() as run_id:
        store.save_snapshots(
            run_id,
            "market",
            [("AAA", "2026-01-01", {"price": 1}), ("BBB", "2026-01-01", {"price": 2})],
        )
    assert store.latest_snapshot("market", "BBB") == {"price": 2}


def test_snapshot_store_records_failure(tmp_path):
    store = SnapshotStore(tmp_path / "snapshots.sqlite3")
    try:
        with store.run():
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert store.run_history()[0]["status"] == "FAILED"
