from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ACTION_PRIORITY = {
    "BUY_CANDIDATE": 5,
    "WATCH": 4,
    "RESEARCH": 3,
    "NO_BUY": 2,
    "AVOID": 1,
}


def format_number(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.1f}"


def format_percent(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):+.1%}"


def format_money(value: Any, currency: str = "USD") -> str:
    if value is None or pd.isna(value):
        return "N/A"
    symbol = "$" if currency == "USD" else f"{currency} "
    return f"{symbol}{float(value):,.2f}"


def _fear_summary(analysis: dict[str, Any]) -> str:
    market = analysis["market"]
    drawdown = format_percent(market.get("drawdown_from_high"))
    relative = format_percent(market.get("relative_return_3m"))
    return f"52周高点回撤 {drawdown}；3个月相对基准 {relative}"


def _fear_classification(analysis: dict[str, Any]) -> str:
    status = analysis["fundamental_status"]
    if status in {"stable", "improving"}:
        return "可能是暂时错价"
    if status == "deteriorating":
        return "结构性风险"
    return "证据不足"


def _value_summary(analysis: dict[str, Any]) -> str:
    valuation = analysis["valuation"]
    value_range = valuation.get("value_range")
    currency = analysis["fundamentals"].get("currency") or "USD"
    if not value_range:
        return "N/A"
    return "/".join(
        format_money(value_range[key], currency) for key in ("bear", "base", "bull")
    )


def _analysis_line(analysis: dict[str, Any]) -> str:
    market = analysis["market"]
    valuation = analysis["valuation"]
    return (
        f"| {analysis['ticker']} | {analysis['action']} | "
        f"{format_money(market.get('current_price'), analysis['fundamentals'].get('currency') or 'USD')} | "
        f"{analysis['combined_score']:.1f} | {market.get('trend', 'UNKNOWN')} | "
        f"{_fear_summary(analysis)} | {_fear_classification(analysis)} | "
        f"{_value_summary(analysis)} | "
        f"{format_percent(valuation.get('base_margin_of_safety_pct'))} | "
        f"{format_percent(valuation.get('expected_annualized_return_5y'))} | "
        f"{analysis.get('failed_gate') or '全部自动门槛通过，仍需人工复核'} |"
    )


def _section_table(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["无。"]
    lines = [
        "| 股票 | 状态 | 价格 | 综合分 | 趋势 | 市场恐惧 | 判断 | Bear/Base/Bull | Base安全边际 | 5年隐含年化 | 未通过门槛 |",
        "|---|---|---:|---:|---|---|---|---|---:|---:|---|",
    ]
    lines.extend(_analysis_line(item) for item in items)
    return lines


def render_markdown(bundle: dict[str, Any], max_candidates: int = 5) -> str:
    metadata = bundle["metadata"]
    analyses = sorted(
        bundle["analyses"],
        key=lambda item: (ACTION_PRIORITY[item["action"]], item["combined_score"]),
        reverse=True,
    )
    buy = [item for item in analyses if item["action"] == "BUY_CANDIDATE"][:max_candidates]
    watch = [item for item in analyses if item["action"] in {"WATCH", "RESEARCH"}][
        :max_candidates
    ]
    no_buy = [item for item in analyses if item["action"] in {"NO_BUY", "AVOID"}][
        :max_candidates
    ]
    conclusion = (
        f"{len(buy)} 个候选通过自动门槛，全部需要人工复核。"
        if buy
        else "今日无可行动的新候选。"
    )
    lines = [
        f"# Quality Mispricing 早报 — {metadata['report_date']}",
        "",
        f"数据截止：{metadata.get('data_cutoff') or 'N/A'}；时区：{metadata['timezone']}；"
        f"基准：{metadata['benchmark']}；市场池：{metadata['universe_size']} 只；"
        f"成功扫描：{metadata.get('market_coverage', metadata['universe_size'])} 只；"
        f"深度分析：{metadata.get('deep_analysis_size', len(analyses))} 只。",
        "",
        "## 今日结论",
        "",
        conclusion,
        "",
        "## 市场扫描漏斗",
        "",
    ]
    scan = bundle.get("market_scan", [])
    if not scan:
        lines.append("今日没有股票通过流动性与至少 10% 回撤的价格预筛。")
    else:
        lines.extend(
            [
                "| 股票 | 预筛分 | 价格 | 52周回撤 | 3个月相对基准 | 趋势 |",
                "|---|---:|---:|---:|---:|---|",
                *[
                    f"| {item['ticker']} | {format_number(item.get('screen_score'))} | "
                    f"{format_money(item.get('current_price'))} | "
                    f"{format_percent(item.get('drawdown_from_high'))} | "
                    f"{format_percent(item.get('relative_return_3m'))} | "
                    f"{item.get('trend', 'UNKNOWN')} |"
                    for item in scan[:10]
                ],
                "",
                "预筛分只决定谁进入财务研究，不是买入评分。",
            ]
        )
    lines.extend([
        "",
        "## Portfolio Alerts",
        "",
    ])
    portfolio = bundle.get("portfolio", [])
    alerts = [row for row in portfolio if row.get("portfolio_alert") != "NO_ALERT"]
    if not portfolio:
        lines.append("持仓文件不可用。")
    elif not alerts:
        lines.append("今日没有触发仓位上限或 -5%/-10%/-15%/-20% 复核阈值。")
    else:
        lines.extend(
            [
                "| 股票 | 权重 | 收益 | 52周回撤 | 提醒 |",
                "|---|---:|---:|---:|---|",
                *[
                    f"| {row['ticker']} | {format_percent(row.get('portfolio_weight'))} | "
                    f"{format_percent(row.get('return_pct'))} | "
                    f"{format_percent(row.get('drawdown_from_high'))} | "
                    f"{row.get('portfolio_alert')} |"
                    for row in alerts
                ],
            ]
        )
    enhancement = bundle.get("index_enhancement", {})
    lines.extend(["", "## 指数增强 / 基准偏离", ""])
    if enhancement.get("status") != "OK":
        lines.append("组合或基准历史数据不足，暂时无法计算指数增强指标。")
    else:
        lines.extend(
            [
                f"基准：{enhancement['benchmark']}；口径：当前静态权重与每日收盘收益。",
                "",
                "| 核心指数仓 | 主动增强仓 | 现金/未配置 | 跟踪误差 | Beta | 相关性 | 12个月超额收益 |",
                "|---:|---:|---:|---:|---:|---:|---:|",
                f"| {format_percent(enhancement.get('core_index_weight'))} | "
                f"{format_percent(enhancement.get('active_sleeve_weight'))} | "
                f"{format_percent(enhancement.get('cash_or_unallocated_weight'))} | "
                f"{format_percent(enhancement.get('tracking_error'))} | "
                f"{format_number(enhancement.get('beta'))} | "
                f"{format_number(enhancement.get('correlation'))} | "
                f"{format_percent(enhancement.get('active_return_12m'))} |",
                "",
                f"最大主动仓：{enhancement.get('largest_active_ticker') or 'N/A'} "
                f"{format_percent(enhancement.get('largest_active_weight'))}。",
            ]
        )
        warning_labels = {
            "ACTIVE_SLEEVE_ABOVE_40_PERCENT": "主动增强仓超过40%，组合已明显偏离纯指数。",
            "SINGLE_ACTIVE_POSITION_ABOVE_10_PERCENT": "单一主动仓超过10%。",
            "TRACKING_ERROR_ABOVE_10_PERCENT": "年化跟踪误差超过10%，相对基准波动较高。",
        }
        for warning in enhancement.get("warnings", []):
            lines.append(f"- {warning_labels.get(warning, warning)}")
        lines.append("- 该层只监控组合偏离，不会自动调仓或覆盖个股基本面结论。")
    lines.extend(["", "## 买入候选（需人工复核）", "", *_section_table(buy)])
    lines.extend(["", "## 观察 / 待研究", "", *_section_table(watch)])
    lines.extend(["", "## 明确不买", "", *_section_table(no_buy)])
    lines.extend(["", "## 深度研究队列（AI Berkshire）", ""])
    research_tasks = bundle.get("research_tasks", [])
    if research_tasks:
        for task in research_tasks:
            lines.append(
                f"- {task['ticker']}：已创建深度研究任务 `{task['task_id'][:8]}`；"
                "须完成一手资料、反方论点、反向 DCF 与人工复核，不构成买入指令。"
            )
    else:
        lines.append("今日没有新建深度研究任务；冷却期内任务不会重复创建。")
    lines.extend(["", "## 今日人工动作", ""])
    if buy:
        for item in buy[:3]:
            lines.append(
                f"- 复核 {item['ticker']} 的最新原始财报、估值假设和 thesis-break 条件；仅限人工决策。"
            )
    elif watch:
        for item in watch[:3]:
            lines.append(f"- 补齐 {item['ticker']} 的 {item.get('failed_gate') or '证据缺口'}。")
    else:
        lines.append("- 无；现金是有效结果。")
    lines.extend(["", "## 数据缺口与风险", ""])
    errors = bundle.get("errors", {})
    if not errors:
        lines.append("- 无抓取错误；估值仍是筛选模型，不替代完整 DCF/分部估值。")
    else:
        displayed_errors = 0
        for category, entries in errors.items():
            for ticker, message in entries.items():
                if displayed_errors >= 20:
                    break
                lines.append(f"- {category}/{ticker}: {message}")
                displayed_errors += 1
        total_errors = sum(len(entries) for entries in errors.values())
        if total_errors > displayed_errors:
            lines.append(f"- 另有 {total_errors - displayed_errors} 个抓取错误，详见 JSON 报告。")
    if not metadata.get("sec_enabled"):
        lines.append("- 未配置 SEC_USER_AGENT：财务数据无法完成一手来源交叉验证，因此不会产生 BUY_CANDIDATE。")
    lines.extend(["", "## Sources", ""])
    universe = bundle.get("universe", {})
    if universe.get("source_url"):
        lines.append(f"- 股票池: [{universe.get('source', 'Universe source')}]({universe['source_url']})")
    if universe.get("constituents_url"):
        lines.append(f"- 成分股镜像: [Constituents table]({universe['constituents_url']})")
    for item in analyses[:15]:
        unique_urls: dict[str, str] = {}
        for source in item.get("sources", []):
            url = source.get("url")
            name = source.get("name") or "Source"
            if url:
                unique_urls[url] = name
        rendered = "；".join(f"[{name}]({url})" for url, name in unique_urls.items())
        lines.append(f"- {item['ticker']}: {rendered or '无可用来源'}")
    lines.extend(
        [
            "",
            "本报告是研究筛选，不构成投资建议；任何买卖均需人工复核。",
            "",
        ]
    )
    return "\n".join(lines)


def audit_report(markdown: str, bundle: dict[str, Any], max_candidates: int) -> list[str]:
    errors: list[str] = []
    required = (
        "## 今日结论",
        "## 市场扫描漏斗",
        "## Portfolio Alerts",
        "## 指数增强 / 基准偏离",
        "## 买入候选（需人工复核）",
        "## 观察 / 待研究",
        "## 明确不买",
        "## 深度研究队列（AI Berkshire）",
        "## 今日人工动作",
        "## 数据缺口与风险",
        "## Sources",
        "不构成投资建议；任何买卖均需人工复核",
    )
    for marker in required:
        if marker not in markdown:
            errors.append(f"missing report marker: {marker}")
    if re.search(r"自动(?:买入|卖出|下单)|直接下单", markdown):
        errors.append("report contains automatic-trading language")
    buy = [item for item in bundle["analyses"] if item["action"] == "BUY_CANDIDATE"][
        :max_candidates
    ]
    for item in buy:
        if not any(source.get("tier") == "primary" for source in item.get("sources", [])):
            errors.append(f"{item['ticker']} buy candidate lacks a primary source")
        if item["valuation"].get("value_range") is None:
            errors.append(f"{item['ticker']} buy candidate lacks a valuation range")
    return errors


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def save_reports(
    bundle: dict[str, Any], reports_dir: str | Path, max_candidates: int
) -> tuple[Path, Path]:
    directory = Path(reports_dir)
    stamp = datetime.fromisoformat(bundle["metadata"]["generated_at"]).strftime("%Y%m%d-%H%M%S")
    markdown_path = directory / f"morning-brief-{stamp}.md"
    json_path = directory / f"morning-brief-{stamp}.json"
    markdown = render_markdown(bundle, max_candidates)
    audit_errors = audit_report(markdown, bundle, max_candidates)
    if audit_errors:
        raise ValueError("Report audit failed: " + "; ".join(audit_errors))
    _atomic_write(markdown_path, markdown)
    _atomic_write(
        json_path,
        json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
    )
    _atomic_write(directory / "latest.md", markdown)
    _atomic_write(
        directory / "latest.json",
        json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
    )
    return markdown_path, json_path


def print_portfolio_report(*args, **kwargs):
    """Deprecated compatibility wrapper for the original console-only version."""
    portfolio = kwargs.get("portfolio")
    if portfolio is None and args:
        portfolio = args[0]
    if portfolio is None:
        return
    print(portfolio.to_string(index=False))


def print_mispricing_ranking(portfolio):
    columns = [column for column in ("ticker", "mispricing_score", "research_priority") if column in portfolio]
    print(portfolio.sort_values("mispricing_score", ascending=False)[columns].to_string(index=False))
