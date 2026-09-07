import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

from research_queue import enqueue_qualified_research, render_research_brief
from settings import Settings
from storage import SnapshotStore


def _settings(tmp_path, **overrides):
    defaults = dict(
        project_dir=tmp_path,
        portfolio_file=tmp_path / "portfolio.csv",
        data_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
        deep_research_enabled=True,
        deep_research_max_new_tasks=1,
        deep_research_cooldown_days=30,
        deep_research_min_combined_score=85,
        deep_research_min_margin_of_safety=0.25,
    )
    return Settings(**(defaults | overrides))


def _analysis(ticker="AAA", score=90, margin=0.30):
    return {
        "ticker": ticker,
        "action": "BUY_CANDIDATE",
        "combined_score": score,
        "risk_flags": [],
        "validation": {"status": "VERIFIED"},
        "market": {"current_price": 100},
        "valuation": {"base_margin_of_safety_pct": margin, "value_range": {"base": 130}},
        "sources": [{"tier": "primary", "url": "https://example.com"}],
    }


def test_queue_creates_only_best_eligible_task_and_honors_cooldown(tmp_path):
    store = SnapshotStore(tmp_path / "db.sqlite3")
    settings = _settings(tmp_path)
    first = enqueue_qualified_research(
        store, "run-1", [_analysis("LOW", 86), _analysis("TOP", 95)], settings
    )
    second = enqueue_qualified_research(store, "run-2", [_analysis("TOP", 95)], settings)
    assert [task["ticker"] for task in first] == ["TOP"]
    assert second == []
    assert store.pending_research_tasks()[0]["ticker"] == "TOP"


def test_queue_rejects_non_verified_or_insufficient_margin(tmp_path):
    store = SnapshotStore(tmp_path / "db.sqlite3")
    settings = _settings(tmp_path)
    bad = _analysis("BAD", margin=0.20)
    assert enqueue_qualified_research(store, "run-1", [bad], settings) == []


def test_rendered_brief_keeps_sources_and_human_decision_boundary(tmp_path):
    store = SnapshotStore(tmp_path / "db.sqlite3")
    task = store.create_research_task("TOP", "run-1", {"reason": "test", "screen_snapshot": {}, "sources": [{"label": "SEC", "url": "https://sec.gov"}], "required_report_sections": ["reverse DCF"]})
    brief = render_research_brief(task)
    assert "https://sec.gov" in brief
    assert "不得下单" in brief
