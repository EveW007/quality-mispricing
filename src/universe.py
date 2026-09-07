from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup


SP500_CONSTITUENTS_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
SP500_INDEX_SOURCE_URL = "https://www.spglobal.com/spdji/en/indices/equity/sp-500/"


def _normalize_ticker(value: str) -> str:
    return value.strip().upper().replace(".", "-")


def _read_cache(path: Path, max_age_hours: int | None = None) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if max_age_hours is not None:
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        if datetime.now(timezone.utc) - modified > timedelta(hours=max_age_hours):
            return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parse_sp500_symbols(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="constituents")
    if table is None:
        raise ValueError("S&P 500 constituents table was not found")
    symbols: list[str] = []
    for row in table.find_all("tr")[1:]:
        cells = row.find_all(["td", "th"])
        if cells:
            symbol = _normalize_ticker(cells[0].get_text(" ", strip=True))
            if symbol:
                symbols.append(symbol)
    result = list(dict.fromkeys(symbols))
    if len(result) < 450:
        raise ValueError(f"S&P 500 constituent count is unexpectedly low: {len(result)}")
    return result


def load_market_universe(
    provider: str,
    required_tickers: Iterable[str],
    cache_dir: str | Path,
    cache_hours: int,
    timeout_seconds: int,
    offline: bool = False,
) -> dict[str, Any]:
    required = [_normalize_ticker(ticker) for ticker in required_tickers if ticker.strip()]
    provider = provider.strip().lower()
    if provider in {"watchlist", "custom"}:
        return {
            "provider": provider,
            "symbols": list(dict.fromkeys(required)),
            "source": "Configured portfolio and watchlist",
            "source_url": None,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    if provider != "sp500":
        raise ValueError("universe_provider must be 'sp500' or 'watchlist'")

    cache_path = Path(cache_dir) / "universe" / "sp500.json"
    cached = _read_cache(cache_path, cache_hours)
    if cached is None and offline:
        cached = _read_cache(cache_path)
    if cached is not None:
        cached["symbols"] = list(dict.fromkeys([*required, *cached.get("symbols", [])]))
        return cached
    if offline:
        raise RuntimeError("No cached S&P 500 universe is available")

    response = requests.get(
        SP500_CONSTITUENTS_URL,
        headers={"User-Agent": "QualityMispricing/0.2 market-research tool"},
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = {
        "provider": "sp500",
        "symbols": list(dict.fromkeys([*required, *parse_sp500_symbols(response.text)])),
        "source": "S&P 500 constituents (Wikipedia mirror); index definition by S&P DJI",
        "source_url": SP500_INDEX_SOURCE_URL,
        "constituents_url": SP500_CONSTITUENTS_URL,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_cache(cache_path, payload)
    return payload
