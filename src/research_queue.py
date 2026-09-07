from __future__ import annotations

from typing import Any

try:
    from .settings import Settings
    from .storage import SnapshotStore
except ImportError:
    from settings import Settings
    from storage import SnapshotStore


def _qualifies(analysis: dict[str, Any], settings: Settings) -> bool:
    return (
        analysis.get("action") == "BUY_CANDIDATE"
        and analysis.get("validation", {}).get("status") == "VERIFIED"
        and not analysis.get("risk_flags")
        and float(analysis.get("combined_score", 0)) >= settings.deep_research_min_combined_score
        and float(analysis.get("valuation", {}).get("base_margin_of_safety_pct") or -1)
        >= settings.deep_research_min_margin_of_safety
    )


def task_payload(analysis: dict[str, Any]) -> dict[str, Any]:
    valuation = analysis["valuation"]
    market = analysis["market"]
    return {
        "reason": "Passed conservative automated promotion gates; requires AI Berkshire deep research.",
        "screen_snapshot": {
            "as_of": analysis.get("as_of"),
            "current_price": market.get("current_price"),
            "drawdown_from_high": market.get("drawdown_from_high"),
            "relative_return_3m": market.get("relative_return_3m"),
            "trend": market.get("trend"),
            "quality_score": analysis.get("quality_score"),
            "combined_score": analysis.get("combined_score"),
            "fundamental_status": analysis.get("fundamental_status"),
            "validation_status": analysis.get("validation", {}).get("status"),
            "bear_base_bull": valuation.get("value_range"),
            "base_margin_of_safety_pct": valuation.get("base_margin_of_safety_pct"),
            "expected_annualized_return_5y": valuation.get("expected_annualized_return_5y"),
        },
        "sources": analysis.get("sources", []),
        "required_report_sections": [
            "information richness and AI limitations",
            "business quality and moat",
            "market fear and strongest counter-thesis",
            "management and capital allocation",
            "thesis-break conditions",
            "reverse DCF and business-driven bear/base/bull valuation",
            "primary-source citations and independent cross-checks",
            "human decision only; no order instruction",
        ],
    }


def enqueue_qualified_research(
    store: SnapshotStore, run_id: str, analyses: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    if not settings.deep_research_enabled or settings.deep_research_max_new_tasks == 0:
        return []
    qualified = sorted(
        (analysis for analysis in analyses if _qualifies(analysis, settings)),
        key=lambda item: (
            -float(item["combined_score"]),
            -float(item["valuation"].get("base_margin_of_safety_pct") or 0),
        ),
    )
    tasks: list[dict[str, Any]] = []
    for analysis in qualified:
        ticker = analysis["ticker"]
        if store.research_task_recently_created(ticker, settings.deep_research_cooldown_days):
            continue
        tasks.append(store.create_research_task(ticker, run_id, task_payload(analysis)))
        if len(tasks) >= settings.deep_research_max_new_tasks:
            break
    return tasks


def render_research_brief(task: dict[str, Any]) -> str:
    """Render a durable hand-off brief for a Codex-led research pass.

    This deliberately contains no buy instruction: the daily model is a
    promotion gate, while the report writer must still independently verify
    the thesis and the valuation inputs.
    """
    payload = task["payload"]
    snapshot = payload["screen_snapshot"]
    lines = [
        f"# AI Berkshire 深度研究任务：{task['ticker']}",
        "",
        f"- 任务 ID：`{task['task_id']}`",
        f"- 创建时间：{task['created_at']}",
        f"- 来源运行：`{task['source_run_id']}`",
        "",
        "## 晋级原因（仅供研究，不是买入结论）",
        "",
        payload["reason"],
        "",
        "## 当日筛选快照",
        "",
    ]
    for key, value in snapshot.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## 报告必须覆盖", ""])
    lines.extend(f"- {section}" for section in payload["required_report_sections"])
    lines.extend(["", "## 已有数据来源（仍须复核）", ""])
    for source in payload.get("sources", []):
        label = source.get("label") or source.get("tier") or "source"
        url = source.get("url")
        lines.append(f"- [{label}]({url})" if url else f"- {label}")
    lines.extend(
        [
            "",
            "## 强制边界",
            "",
            "- 先验证 SEC/公司 IR 一手文件；无法验证时不得给出 BUY_CANDIDATE。",
            "- 必须写出最强反方观点、论点失效条件、以及估值假设的敏感性。",
            "- 只给人工复核后的行动区间；不得下单或给出自动交易指令。",
        ]
    )
    return "\n".join(lines) + "\n"
