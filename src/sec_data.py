from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable

import requests

try:
    from .cache import JsonFileCache
except ImportError:  # direct execution from src/
    from cache import JsonFileCache


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


CONCEPTS = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ),
    "operating_income": ("OperatingIncomeLoss",),
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "diluted_eps": ("EarningsPerShareDiluted",),
}


class SecClient:
    def __init__(
        self,
        cache_dir: str | Path,
        user_agent: str,
        timeout_seconds: int = 20,
        cache_hours: int = 168,
    ):
        if "@" not in user_agent:
            raise ValueError("SEC_USER_AGENT must identify a contact email")
        self.cache = JsonFileCache(Path(cache_dir) / "sec")
        self.timeout_seconds = timeout_seconds
        self.max_age = timedelta(hours=cache_hours)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "data.sec.gov",
            }
        )

    def _get_json(self, url: str, cache_key: str, offline: bool = False) -> Any:
        cached = self.cache.get(cache_key, self.max_age)
        if cached is not None:
            return cached
        stale = self.cache.get(cache_key)
        if offline:
            if stale is not None:
                return stale
            raise RuntimeError(f"No cached SEC data for {cache_key}")
        headers = dict(self.session.headers)
        if url == SEC_TICKERS_URL:
            headers["Host"] = "www.sec.gov"
        response = self.session.get(url, headers=headers, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        self.cache.set(cache_key, payload)
        return payload

    def ticker_to_cik(self, ticker: str, offline: bool = False) -> str | None:
        payload = self._get_json(SEC_TICKERS_URL, "company_tickers", offline)
        ticker = ticker.upper()
        for record in payload.values():
            if str(record.get("ticker", "")).upper() == ticker:
                return str(record["cik_str"]).zfill(10)
        return None

    def company_facts(self, ticker: str, offline: bool = False) -> tuple[str, dict[str, Any]]:
        cik = self.ticker_to_cik(ticker, offline)
        if cik is None:
            raise ValueError(f"SEC CIK not found for {ticker}")
        payload = self._get_json(
            SEC_FACTS_URL.format(cik=cik), f"companyfacts_{cik}", offline
        )
        return cik, payload


def _annual_values(
    us_gaap: dict[str, Any], concepts: Iterable[str], unit: str
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for concept in concepts:
        units = us_gaap.get(concept, {}).get("units", {})
        entries = units.get(unit, [])
        if not entries:
            continue
        by_end: dict[str, dict[str, Any]] = {}
        for entry in entries:
            form = str(entry.get("form", ""))
            if entry.get("fp") != "FY" or form not in {"10-K", "10-K/A", "20-F", "20-F/A"}:
                continue
            end = entry.get("end")
            if not end:
                continue
            previous = by_end.get(end)
            if previous is None or str(entry.get("filed", "")) > str(previous.get("filed", "")):
                by_end[end] = entry
        if by_end:
            selected = sorted(by_end.values(), key=lambda item: item["end"])
            break
    return selected[-6:]


def normalized_sec_fundamentals(
    ticker: str, cik: str, payload: dict[str, Any]
) -> dict[str, Any]:
    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    annual: dict[str, list[dict[str, Any]]] = {}
    for metric, concepts in CONCEPTS.items():
        unit = "USD/shares" if metric == "diluted_eps" else "USD"
        annual[metric] = _annual_values(us_gaap, concepts, unit)

    periods: dict[str, dict[str, Any]] = {}
    for metric, entries in annual.items():
        for entry in entries:
            period = periods.setdefault(entry["end"], {"period_end": entry["end"]})
            period[metric] = entry.get("val")
            period["filed"] = max(str(period.get("filed", "")), str(entry.get("filed", "")))
    rows = sorted(periods.values(), key=lambda item: item["period_end"])[-6:]
    for row in rows:
        operating_cash_flow = row.get("operating_cash_flow")
        capex = row.get("capex")
        row["free_cash_flow"] = (
            None
            if operating_cash_flow is None or capex is None
            else operating_cash_flow - capex
        )
    return {
        "ticker": ticker.upper(),
        "cik": cik,
        "company_name": payload.get("entityName"),
        "annual": rows,
        "source": "SEC EDGAR Company Facts",
        "source_tier": "primary",
        "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
        "filings_url": f"https://www.sec.gov/edgar/browse/?CIK={int(cik)}",
    }


def fetch_sec_fundamentals(
    client: SecClient, ticker: str, offline: bool = False
) -> dict[str, Any]:
    cik, payload = client.company_facts(ticker, offline)
    return normalized_sec_fundamentals(ticker, cik, payload)
