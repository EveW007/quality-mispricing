from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf


def calculate_return(series: pd.Series, days: int) -> float | None:
    clean = series.dropna()
    if len(clean) <= days:
        return None
    return float(clean.iloc[-1] / clean.iloc[-days - 1] - 1)


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _cache_path(cache_dir: Path, ticker: str) -> Path:
    safe_ticker = ticker.replace("/", "-").replace("^", "INDEX-")
    return cache_dir / f"{safe_ticker}.csv"


def _cache_is_fresh(path: Path, hours: int) -> bool:
    if not path.exists():
        return False
    modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return datetime.now(timezone.utc) - modified <= timedelta(hours=hours)


def _read_history(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index, utc=True)
    return frame


def _write_history(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    frame.to_csv(temporary)
    temporary.replace(path)


def fetch_price_history(
    ticker: str,
    period: str = "5y",
    cache_dir: str | Path | None = None,
    cache_hours: int = 8,
    offline: bool = False,
    attempts: int = 3,
) -> pd.DataFrame:
    ticker = ticker.strip().upper()
    cache_path = None if cache_dir is None else _cache_path(Path(cache_dir), ticker)
    if cache_path is not None and (_cache_is_fresh(cache_path, cache_hours) or offline):
        cached = _read_history(cache_path)
        if not cached.empty:
            return cached
    if offline:
        raise RuntimeError(f"No cached market data for {ticker}")

    error: Exception | None = None
    for attempt in range(attempts):
        try:
            frame = yf.Ticker(ticker).history(period=period, auto_adjust=False)
            if frame.empty:
                raise ValueError(f"No market data found for {ticker}")
            frame.index = pd.to_datetime(frame.index, utc=True)
            if cache_path is not None:
                _write_history(cache_path, frame)
            return frame
        except Exception as exc:  # provider/network exceptions vary by version
            error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"Market data failed for {ticker}: {error}") from error


def fetch_universe_history(
    tickers: Iterable[str],
    period: str,
    cache_dir: str | Path,
    cache_hours: int,
    offline: bool = False,
    workers: int = 6,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    unique = tuple(dict.fromkeys(ticker.strip().upper() for ticker in tickers if ticker.strip()))
    histories: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    directory = Path(cache_dir)
    missing: list[str] = []
    for ticker in unique:
        path = _cache_path(directory, ticker)
        if path.exists() and (_cache_is_fresh(path, cache_hours) or offline):
            try:
                cached = _read_history(path)
            except Exception:
                cached = pd.DataFrame()
            if not cached.empty:
                histories[ticker] = cached
                continue
        missing.append(ticker)
    if offline:
        errors.update({ticker: f"No cached market data for {ticker}" for ticker in missing})
        return histories, errors

    for start in range(0, len(missing), 40):
        chunk = missing[start : start + 40]
        if len(chunk) < 2:
            continue
        try:
            downloaded = _download_batch(chunk, period)
        except Exception:
            continue
        for ticker, frame in downloaded.items():
            histories[ticker] = frame
            _write_history(_cache_path(directory, ticker), frame)

    remaining = [ticker for ticker in missing if ticker not in histories]
    with ThreadPoolExecutor(max_workers=min(workers, max(1, len(unique)))) as executor:
        futures = {
            executor.submit(
                fetch_price_history,
                ticker,
                period,
                cache_dir,
                cache_hours,
                offline,
            ): ticker
            for ticker in remaining
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                histories[ticker] = future.result()
            except Exception as exc:
                errors[ticker] = str(exc)
    return histories, errors


def _download_batch(tickers: list[str], period: str, attempts: int = 2) -> dict[str, pd.DataFrame]:
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            raw = yf.download(
                tickers=tickers,
                period=period,
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False,
            )
            if raw.empty:
                raise ValueError("batch market download returned no data")
            result: dict[str, pd.DataFrame] = {}
            for ticker in tickers:
                if not isinstance(raw.columns, pd.MultiIndex):
                    frame = raw.copy() if len(tickers) == 1 else pd.DataFrame()
                elif ticker in raw.columns.get_level_values(0):
                    frame = raw[ticker].copy()
                elif ticker in raw.columns.get_level_values(-1):
                    frame = raw.xs(ticker, axis=1, level=-1).copy()
                else:
                    frame = pd.DataFrame()
                frame = frame.dropna(how="all")
                if not frame.empty and "Close" in frame:
                    frame.index = pd.to_datetime(frame.index, utc=True)
                    result[ticker] = frame
            return result
        except Exception as exc:
            error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"Batch market data failed: {error}") from error


def _relative_return(
    stock_close: pd.Series, benchmark_close: pd.Series, days: int
) -> float | None:
    stock_close = stock_close.copy()
    benchmark_close = benchmark_close.copy()
    stock_close.index = pd.to_datetime(stock_close.index, utc=True).normalize()
    benchmark_close.index = pd.to_datetime(benchmark_close.index, utc=True).normalize()
    stock_close = stock_close.groupby(level=0).last()
    benchmark_close = benchmark_close.groupby(level=0).last()
    aligned = pd.concat(
        [stock_close.rename("stock"), benchmark_close.rename("benchmark")], axis=1
    ).dropna()
    stock_return = calculate_return(aligned["stock"], days)
    benchmark_return = calculate_return(aligned["benchmark"], days)
    if stock_return is None or benchmark_return is None:
        return None
    return stock_return - benchmark_return


def analyze_price_history(
    ticker: str,
    history: pd.DataFrame,
    benchmark_history: pd.DataFrame | None = None,
) -> dict[str, object]:
    if history.empty or "Close" not in history:
        raise ValueError(f"No usable close history for {ticker}")
    close = history["Close"].dropna()
    high = history["High"].dropna() if "High" in history else close
    if close.empty:
        raise ValueError(f"No usable close history for {ticker}")

    current = _finite(close.iloc[-1])
    high_52w = _finite(high.tail(252).max())
    sma_50 = _finite(close.tail(50).mean()) if len(close) >= 50 else None
    sma_200 = _finite(close.tail(200).mean()) if len(close) >= 200 else None
    if current is not None and sma_50 is not None and sma_200 is not None:
        if current > sma_50 > sma_200:
            trend = "UPTREND"
        elif current < sma_50 < sma_200:
            trend = "DOWNTREND"
        else:
            trend = "MIXED"
    else:
        trend = "UNKNOWN"

    daily_returns = close.pct_change().dropna().tail(63)
    volatility = (
        _finite(daily_returns.std() * math.sqrt(252)) if len(daily_returns) >= 20 else None
    )
    benchmark_close = None
    if benchmark_history is not None and "Close" in benchmark_history:
        benchmark_close = benchmark_history["Close"].dropna()
    average_dollar_volume = None
    if "Volume" in history:
        volume = history["Volume"].reindex(close.index).dropna().tail(20)
        prices = close.reindex(volume.index)
        if not volume.empty:
            average_dollar_volume = _finite((prices * volume).mean())

    result: dict[str, object] = {
        "ticker": ticker.upper(),
        "as_of": close.index[-1].isoformat(),
        "current_price": current,
        "high_52w": high_52w,
        "drawdown_from_high": (
            None if current is None or not high_52w else current / high_52w - 1
        ),
        "return_5d": calculate_return(close, 5),
        "return_1m": calculate_return(close, 21),
        "return_3m": calculate_return(close, 63),
        "return_6m": calculate_return(close, 126),
        "return_12m": calculate_return(close, 252),
        "sma_50": sma_50,
        "sma_200": sma_200,
        "distance_to_sma_50": None if current is None or not sma_50 else current / sma_50 - 1,
        "distance_to_sma_200": None if current is None or not sma_200 else current / sma_200 - 1,
        "annualized_volatility_3m": volatility,
        "average_dollar_volume_20d": average_dollar_volume,
        "trend": trend,
        "source": "Yahoo Finance via yfinance",
        "source_url": f"https://finance.yahoo.com/quote/{ticker.upper()}/history",
    }
    if benchmark_close is not None:
        result["relative_return_3m"] = _relative_return(close, benchmark_close, 63)
        result["relative_return_6m"] = _relative_return(close, benchmark_close, 126)
    else:
        result["relative_return_3m"] = None
        result["relative_return_6m"] = None
    return result


def market_dislocation_score(market: dict[str, object]) -> float:
    drawdown = _finite(market.get("drawdown_from_high")) or 0.0
    relative = _finite(market.get("relative_return_3m")) or 0.0
    distance_200 = _finite(market.get("distance_to_sma_200")) or 0.0
    return_1m = _finite(market.get("return_1m")) or 0.0
    drawdown_score = min(max(-drawdown, 0.0), 0.60) / 0.60 * 55
    relative_score = min(max(-relative, 0.0), 0.30) / 0.30 * 20
    below_sma_score = min(max(-distance_200, 0.0), 0.30) / 0.30 * 10
    stabilization_score = min(max(return_1m, 0.0), 0.15) / 0.15 * 15
    return round(drawdown_score + relative_score + below_sma_score + stabilization_score, 1)


def rank_market_scan(
    market_packages: dict[str, dict[str, object]],
    min_average_dollar_volume: float,
    limit: int,
) -> list[dict[str, object]]:
    ranked: list[dict[str, object]] = []
    for ticker, market in market_packages.items():
        price = _finite(market.get("current_price"))
        drawdown = _finite(market.get("drawdown_from_high"))
        liquidity = _finite(market.get("average_dollar_volume_20d"))
        if (
            price is None
            or price < 5
            or drawdown is None
            or drawdown > -0.10
            or liquidity is None
            or liquidity < min_average_dollar_volume
        ):
            continue
        ranked.append(
            {
                "ticker": ticker,
                "screen_score": market_dislocation_score(market),
                "current_price": price,
                "drawdown_from_high": drawdown,
                "relative_return_3m": market.get("relative_return_3m"),
                "trend": market.get("trend"),
                "average_dollar_volume_20d": liquidity,
                "as_of": market.get("as_of"),
                "source_url": market.get("source_url"),
            }
        )
    return sorted(ranked, key=lambda item: (-float(item["screen_score"]), str(item["ticker"])))[:limit]


def get_market_data(ticker: str) -> dict[str, object]:
    """Backward-compatible one-ticker helper used by early project code."""
    history = fetch_price_history(ticker, period="1y")
    return analyze_price_history(ticker, history)


def get_valuation_data(ticker: str) -> dict[str, object]:
    info = yf.Ticker(ticker).info
    return {
        "ticker": ticker.upper(),
        "trailing_pe": _finite(info.get("trailingPE")),
        "forward_pe": _finite(info.get("forwardPE")),
    }


def get_historical_pe_data(ticker: str, period: str = "5y") -> dict[str, object]:
    stock = yf.Ticker(ticker)
    history = stock.history(period=period, auto_adjust=False)
    if history.empty:
        raise ValueError(f"No price history found for {ticker}")
    income_statement = stock.quarterly_income_stmt
    if income_statement.empty:
        raise ValueError(f"No income statement found for {ticker}")
    return {
        "ticker": ticker.upper(),
        "price_history": history,
        "income_statement": income_statement,
    }
