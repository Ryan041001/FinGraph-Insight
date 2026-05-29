from __future__ import annotations

import time
from threading import RLock
from typing import Any

from app.services.graph_store import graph_store


_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = RLock()
_DEFAULT_TTL_SECONDS = 12 * 3600


def enrich_company_by_stock_code(
    stock_code: str,
    company_name: str | None = None,
    market: str = "A",
    ttl_seconds: int | None = None,
) -> dict[str, Any] | None:
    """Fetch fundamentals from yfinance, cache it, and back-fill graph_store."""

    cleaned = (stock_code or "").strip()
    if not cleaned:
        return None

    cache_key = f"{market.upper()}:{cleaned}"
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached and cached[0] > now:
            payload = dict(cached[1])
            _backfill_graph(company_name, payload)
            return payload

    payload = _fetch_yfinance_info(cleaned, market)
    if payload is None:
        return None

    ttl = ttl_seconds if ttl_seconds is not None else _DEFAULT_TTL_SECONDS
    with _CACHE_LOCK:
        _CACHE[cache_key] = (now + ttl, payload)

    _backfill_graph(company_name, payload)
    return dict(payload)


def reset_enrichment_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def _fetch_yfinance_info(stock_code: str, market: str) -> dict[str, Any] | None:
    try:
        import yfinance as yf
    except ImportError:
        return None

    symbol = _yahoo_symbol(stock_code, market)
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception:
        return None

    payload: dict[str, Any] = {
        "symbol": symbol,
        "long_name": info.get("longName"),
        "short_name": info.get("shortName"),
        "industry": info.get("industry"),
        "sector": info.get("sector"),
        "website": info.get("website"),
        "country": info.get("country"),
        "employees": info.get("fullTimeEmployees"),
        "business_summary": info.get("longBusinessSummary"),
        "market_cap": info.get("marketCap"),
        "currency": info.get("currency"),
        "source": "yfinance",
    }
    if not any(value for key, value in payload.items() if key not in {"symbol", "source"}):
        return None
    return payload


def _yahoo_symbol(stock_code: str, market: str) -> str:
    market_normalized = market.upper()
    if market_normalized == "HK":
        return f"{stock_code.zfill(4)}.HK"
    normalized = stock_code.zfill(6)
    suffix = "SS" if normalized.startswith(("5", "6", "9")) else "SZ"
    return f"{normalized}.{suffix}"


def _backfill_graph(company_name: str | None, payload: dict[str, Any]) -> None:
    if not company_name:
        return
    try:
        node = graph_store._find_company(company_name.strip())
    except AttributeError:
        return
    if node is None:
        return

    industry = payload.get("industry") or ""
    sector = payload.get("sector") or ""
    website = payload.get("website") or ""
    long_name = payload.get("long_name") or ""
    summary = payload.get("business_summary") or ""

    if not any([industry, sector, website, long_name, summary]):
        return

    merged_properties = dict(node.properties)
    if industry and merged_properties.get("industry") in {None, "", "未知"}:
        merged_properties["industry"] = industry
    if sector:
        merged_properties.setdefault("sector", sector)
    if website:
        merged_properties.setdefault("website", website)
    if long_name:
        merged_properties.setdefault("long_name", long_name)
    if summary:
        merged_properties.setdefault("business_summary", summary)

    if merged_properties == node.properties:
        return

    with graph_store._lock:
        graph_store._nodes[node.id] = node.model_copy(update={"properties": merged_properties})
