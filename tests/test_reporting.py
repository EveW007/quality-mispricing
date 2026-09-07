import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

from reporting import audit_report, render_markdown


def test_empty_report_is_valid_and_explicit():
    bundle = {
        "metadata": {
            "report_date": "2026-08-12",
            "data_cutoff": "2026-08-11",
            "timezone": "Asia/Singapore",
            "benchmark": "SPY",
            "universe_size": 0,
            "sec_enabled": False,
        },
        "portfolio": [],
        "analyses": [],
        "errors": {},
    }
    markdown = render_markdown(bundle)
    assert "今日无可行动的新候选" in markdown
    assert not audit_report(markdown, bundle, 5)


def test_report_caps_displayed_buy_candidates_before_audit():
    def candidate(number):
        return {
            "ticker": f"T{number}",
            "action": "BUY_CANDIDATE",
            "combined_score": 90,
            "fundamental_status": "stable",
            "failed_gate": None,
            "market": {
                "current_price": 100,
                "trend": "MIXED",
                "drawdown_from_high": -0.2,
                "relative_return_3m": -0.1,
            },
            "fundamentals": {"currency": "USD"},
            "valuation": {
                "value_range": {"bear": 90, "base": 130, "bull": 160},
                "base_margin_of_safety_pct": 0.3,
                "expected_annualized_return_5y": 0.05,
            },
            "sources": [{"tier": "primary", "url": "https://www.sec.gov"}],
        }

    bundle = {
        "metadata": {
            "report_date": "2026-08-16",
            "data_cutoff": "2026-08-15",
            "timezone": "Asia/Singapore",
            "benchmark": "SPY",
            "universe_size": 6,
            "sec_enabled": True,
        },
        "portfolio": [],
        "analyses": [candidate(number) for number in range(6)],
        "errors": {},
    }
    markdown = render_markdown(bundle, 5)
    assert markdown.count("| BUY_CANDIDATE |") == 5
    assert not audit_report(markdown, bundle, 5)
