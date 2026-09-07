from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

try:
    from .analysis import analyze_company
    from .fundamentals import fetch_universe_fundamentals
    from .market_data import analyze_price_history, fetch_universe_history, rank_market_scan
    from .portfolio import (
        analyze_index_enhancement,
        calculate_position_metrics,
        load_portfolio,
        position_alert,
    )
    from .reporting import save_reports
    from .research_queue import enqueue_qualified_research
    from .sec_data import SecClient
    from .settings import Settings
    from .storage import SnapshotStore
    from .universe import load_market_universe
except ImportError:
    from analysis import analyze_company
    from fundamentals import fetch_universe_fundamentals
    from market_data import analyze_price_history, fetch_universe_history, rank_market_scan
    from portfolio import (
        analyze_index_enhancement,
        calculate_position_metrics,
        load_portfolio,
        position_alert,
    )
    from reporting import save_reports
    from research_queue import enqueue_qualified_research
    from sec_data import SecClient
    from settings import Settings
    from storage import SnapshotStore
    from universe import load_market_universe


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    clean = frame.where(pd.notna(frame), None)
    return clean.to_dict(orient="records")


def run_daily_pipeline(
    settings: Settings,
    offline: bool = False,
    skip_sec: bool = False,
) -> dict[str, Any]:
    settings.ensure_directories()
    store = SnapshotStore(settings.database_path)

    with store.run() as run_id:
        portfolio = load_portfolio(settings.portfolio_file)
        required_tickers = tuple(
            dict.fromkeys([*portfolio["ticker"].tolist(), *settings.watchlist])
        )
        universe = load_market_universe(
            settings.universe_provider,
            required_tickers,
            settings.cache_dir,
            settings.universe_cache_hours,
            settings.request_timeout_seconds,
            offline,
        )
        scan_tickers = tuple(universe["symbols"])
        all_market_tickers = tuple(dict.fromkeys([settings.benchmark, *scan_tickers]))
        histories, market_errors = fetch_universe_history(
            all_market_tickers,
            settings.history_period,
            settings.cache_dir / "market",
            settings.market_cache_hours,
            offline,
        )
        benchmark_history = histories.get(settings.benchmark)
        if benchmark_history is None:
            raise RuntimeError(
                f"Benchmark {settings.benchmark} is unavailable: "
                f"{market_errors.get(settings.benchmark, 'unknown error')}"
            )
        market_packages: dict[str, dict[str, Any]] = {}
        for ticker in scan_tickers:
            history = histories.get(ticker)
            if history is None:
                continue
            try:
                market_packages[ticker] = analyze_price_history(
                    ticker, history, benchmark_history
                )
            except Exception as exc:
                market_errors[ticker] = str(exc)
        minimum_success = max(1, int(len(scan_tickers) * 0.80))
        if len(market_packages) < minimum_success:
            raise RuntimeError(
                f"Market scan coverage too low: {len(market_packages)}/{len(scan_tickers)}"
            )
        benchmark_package = analyze_price_history(
            settings.benchmark, benchmark_history, benchmark_history
        )
        store.save_snapshots(
            run_id,
            "market",
            [
                (settings.benchmark, str(benchmark_package["as_of"]), benchmark_package),
                *[
                    (ticker, str(market["as_of"]), market)
                    for ticker, market in market_packages.items()
                ],
            ],
        )
        market_scan = rank_market_scan(
            market_packages,
            settings.min_average_dollar_volume,
            max(20, settings.deep_candidate_limit * 3),
        )
        deep_tickers = tuple(
            dict.fromkeys(
                [
                    *required_tickers,
                    *[item["ticker"] for item in market_scan[: settings.deep_candidate_limit]],
                ]
            )
        )
        deep_market_packages = {
            ticker: market_packages[ticker]
            for ticker in deep_tickers
            if ticker in market_packages
        }

        sec_client = None
        if settings.sec_user_agent and not skip_sec:
            sec_client = SecClient(
                settings.cache_dir,
                settings.sec_user_agent,
                settings.request_timeout_seconds,
                settings.sec_cache_hours,
            )
        fundamental_packages, fundamental_errors = fetch_universe_fundamentals(
            deep_market_packages.keys(),
            settings.cache_dir,
            settings.fundamentals_cache_hours,
            sec_client,
            offline,
        )

        analyses: list[dict[str, Any]] = []
        for ticker, market in deep_market_packages.items():
            fundamental_package = fundamental_packages.get(ticker)
            if fundamental_package is None:
                continue
            analysis = analyze_company(
                ticker, market, fundamental_package, histories[ticker]
            )
            analyses.append(analysis)
            store.save_snapshot(
                run_id,
                "fundamentals",
                ticker,
                str(fundamental_package["metrics"].get("as_of") or market["as_of"]),
                fundamental_package,
            )
            store.save_snapshot(run_id, "analysis", ticker, str(market["as_of"]), analysis)
        if not analyses:
            raise RuntimeError("No company analysis could be produced")

        current_prices = {
            ticker: package.get("current_price") for ticker, package in market_packages.items()
        }
        portfolio["current_price"] = portfolio["ticker"].map(current_prices)
        missing_prices = portfolio.loc[portfolio["current_price"].isna(), "ticker"].tolist()
        if missing_prices:
            raise RuntimeError("Missing market prices for portfolio: " + ", ".join(missing_prices))
        portfolio = calculate_position_metrics(
            portfolio,
            settings.total_account_value,
            settings.cash_balance,
        )
        portfolio["drawdown_from_high"] = portfolio["ticker"].map(
            {ticker: package.get("drawdown_from_high") for ticker, package in market_packages.items()}
        )
        portfolio["portfolio_alert"] = portfolio.apply(position_alert, axis=1)
        index_enhancement = analyze_index_enhancement(
            portfolio, histories, settings.benchmark
        )
        portfolio_records = _records(portfolio)
        for record in portfolio_records:
            as_of = market_packages[record["ticker"]]["as_of"]
            store.save_snapshot(run_id, "portfolio", record["ticker"], str(as_of), record)

        now = datetime.now(ZoneInfo(settings.timezone))
        cutoffs = [item["as_of"] for item in market_packages.values() if item.get("as_of")]
        research_tasks = enqueue_qualified_research(store, run_id, analyses, settings)
        bundle = {
            "metadata": {
                "run_id": run_id,
                "generated_at": now.isoformat(),
                "report_date": now.date().isoformat(),
                "data_cutoff": max(cutoffs) if cutoffs else None,
                "timezone": settings.timezone,
                "benchmark": settings.benchmark,
                "universe_size": len(scan_tickers),
                "market_coverage": len(market_packages),
                "deep_analysis_size": len(analyses),
                "portfolio_file": str(settings.portfolio_file),
                "sec_enabled": sec_client is not None,
                "offline": offline,
            },
            "portfolio": portfolio_records,
            "index_enhancement": index_enhancement,
            "analyses": analyses,
            "research_tasks": research_tasks,
            "market_scan": market_scan[:20],
            "universe": {
                key: value for key, value in universe.items() if key != "symbols"
            },
            "errors": {
                category: errors
                for category, errors in (
                    ("market", market_errors),
                    ("fundamentals", fundamental_errors),
                )
                if errors
            },
        }
        markdown_path, json_path = save_reports(
            bundle, settings.reports_dir, settings.max_candidates
        )
        bundle["report_paths"] = {
            "markdown": str(markdown_path),
            "json": str(json_path),
        }
        store.save_snapshot(run_id, "run", "ALL", now.isoformat(), bundle)
        return bundle
