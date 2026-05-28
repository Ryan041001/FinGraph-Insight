import copy
import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone
from collections.abc import Callable
from pathlib import Path
from threading import RLock

import httpx
import pandas as pd

from app.config import PROJECT_ROOT, settings


class MarketDataError(RuntimeError):
    pass


_KLINE_CACHE: dict[tuple[str, str, str, str | None, str | None, str], tuple[float, dict]] = {}
_KLINE_CACHE_LOCK = RLock()


def build_kline_response(
    stock_code: str,
    market: str = "A",
    period: str = "daily",
    start_date: str | None = None,
    end_date: str | None = None,
    adjust: str = "qfq",
    fetcher: Callable[..., pd.DataFrame] | None = None,
    fallback_fetcher: Callable[..., pd.DataFrame] | None = None,
) -> dict:
    cache_key = _kline_cache_key(stock_code, market, period, start_date, end_date, adjust)
    cache_enabled = _kline_cache_enabled(fetcher, fallback_fetcher)
    if cache_enabled:
        cached_payload = _get_cached_kline(cache_key)
        if cached_payload is not None:
            return cached_payload

    if fetcher is not None:
        fetchers: list[tuple[str, Callable[..., pd.DataFrame]]] = [("akshare", fetcher)]
    else:
        fetchers = [
            ("yfinance", fetch_yfinance_kline),
            ("yahoo_chart", fetch_yahoo_kline),
            ("akshare", fetch_akshare_kline),
        ]

    if fallback_fetcher is not None:
        fetchers.append(("yahoo_chart", fallback_fetcher))

    errors: list[str] = []
    for data_source, resolved_fetcher in fetchers:
        try:
            frame = resolved_fetcher(
                stock_code=stock_code,
                market=market,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
            kline_data = normalize_kline_frame(frame)
            if not kline_data:
                raise MarketDataError(f"No market data returned for {stock_code}")
            payload = _kline_payload(
                stock_code=stock_code,
                market=market,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
                kline_data=kline_data,
                cached=False,
                data_source=data_source,
            )
            if cache_enabled:
                _set_cached_kline(cache_key, payload)
            return payload
        except Exception as exc:
            errors.append(f"{data_source}: {exc}")

    if cache_enabled:
        stale_payload = _get_cached_kline(cache_key, allow_stale=True)
        if stale_payload is not None:
            stale_payload["source_errors"] = errors
            return stale_payload

    raise MarketDataError("; ".join(errors))


def fetch_akshare_kline(**kwargs) -> pd.DataFrame:
    import akshare as ak

    start = kwargs.get("start_date") or (date.today() - timedelta(days=180)).strftime("%Y%m%d")
    end = kwargs.get("end_date") or date.today().strftime("%Y%m%d")
    start = str(start).replace("-", "")
    end = str(end).replace("-", "")
    return ak.stock_zh_a_hist(
        symbol=kwargs["stock_code"],
        period=kwargs.get("period", "daily"),
        start_date=start,
        end_date=end,
        adjust=kwargs.get("adjust", "qfq"),
    )


def fetch_yfinance_kline(**kwargs) -> pd.DataFrame:
    import yfinance as yf

    symbol = _yahoo_symbol(str(kwargs["stock_code"]), str(kwargs.get("market", "A")))
    start_date = _parse_date(kwargs.get("start_date"), date.today() - timedelta(days=180))
    end_date = _parse_date(kwargs.get("end_date"), date.today())
    interval = {"daily": "1d", "weekly": "1wk", "monthly": "1mo"}.get(str(kwargs.get("period", "daily")), "1d")
    frame = yf.download(
        symbol,
        start=start_date.isoformat(),
        end=(end_date + timedelta(days=1)).isoformat(),
        interval=interval,
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if frame is None or frame.empty:
        raise MarketDataError(f"No yfinance market data returned for {symbol}")

    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [str(column[0]) for column in frame.columns]

    rows = []
    for _, row in frame.reset_index().fillna(0).iterrows():
        row_date = _field(row, "Date", "Datetime", "date")
        if hasattr(row_date, "date"):
            normalized_date = row_date.date().isoformat()
        else:
            normalized_date = str(row_date)
        rows.append(
            {
                "date": normalized_date,
                "open": float(_field(row, "Open", "open")),
                "close": float(_field(row, "Close", "close")),
                "high": float(_field(row, "High", "high")),
                "low": float(_field(row, "Low", "low")),
                "volume": int(float(_field(row, "Volume", "volume"))),
                "amount": 0,
            }
        )
    return pd.DataFrame(rows)


def fetch_yahoo_kline(**kwargs) -> pd.DataFrame:
    symbol = _yahoo_symbol(str(kwargs["stock_code"]), str(kwargs.get("market", "A")))
    start_date = _parse_date(kwargs.get("start_date"), date.today() - timedelta(days=180))
    end_date = _parse_date(kwargs.get("end_date"), date.today())
    interval = {"daily": "1d", "weekly": "1wk", "monthly": "1mo"}.get(str(kwargs.get("period", "daily")), "1d")
    period1 = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    period2 = int(datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).timestamp())
    response = httpx.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        params={"period1": period1, "period2": period2, "interval": interval, "events": "history"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=20.0,
    )
    response.raise_for_status()
    payload = response.json()
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise MarketDataError(str(chart["error"]))
    result = (chart.get("result") or [{}])[0]
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    rows = []
    for index, timestamp in enumerate(timestamps):
        rows.append(
            {
                "date": datetime.fromtimestamp(int(timestamp), tz=timezone.utc).date().isoformat(),
                "open": _value_at(quote.get("open"), index),
                "close": _value_at(quote.get("close"), index),
                "high": _value_at(quote.get("high"), index),
                "low": _value_at(quote.get("low"), index),
                "volume": _value_at(quote.get("volume"), index),
                "amount": 0,
            }
        )
    return pd.DataFrame(rows)


def normalize_kline_frame(frame: pd.DataFrame) -> list[dict]:
    points: list[dict] = []
    for _, row in frame.fillna(0).iterrows():
        points.append(
            {
                "date": str(_field(row, "日期", "date")),
                "open": float(_field(row, "开盘", "open")),
                "close": float(_field(row, "收盘", "close")),
                "high": float(_field(row, "最高", "high")),
                "low": float(_field(row, "最低", "low")),
                "volume": int(float(_field(row, "成交量", "volume"))),
                "amount": float(_field(row, "成交额", "amount")),
            }
        )
    return points


def _kline_payload(
    stock_code: str,
    market: str,
    period: str,
    start_date: str | None,
    end_date: str | None,
    adjust: str,
    kline_data: list[dict],
    cached: bool,
    data_source: str,
) -> dict:
    return {
        "stock_code": stock_code,
        "market": market,
        "display_code": f"{stock_code}.SH" if market == "A" and stock_code.startswith("6") else stock_code,
        "company_name": stock_code,
        "period": period,
        "adjust": adjust,
        "cached": cached,
        "data_source": data_source,
        "start_date": start_date,
        "end_date": end_date,
        "kline_data": kline_data,
        "events": [],
    }


def _field(row, *names: str):
    for name in names:
        if name in row:
            return row[name]
    return 0


def _parse_date(value: object, default: date) -> date:
    if value is None:
        return default
    normalized = str(value).replace("-", "")
    return datetime.strptime(normalized, "%Y%m%d").date()


def _yahoo_symbol(stock_code: str, market: str) -> str:
    if market.upper() == "HK":
        return f"{stock_code.zfill(4)}.HK"
    normalized = stock_code.zfill(6)
    suffix = "SS" if normalized.startswith(("5", "6", "9")) else "SZ"
    return f"{normalized}.{suffix}"


def _value_at(values: object, index: int) -> float:
    if not isinstance(values, list) or index >= len(values) or values[index] is None:
        return 0
    return float(values[index])


def _kline_cache_key(
    stock_code: str,
    market: str,
    period: str,
    start_date: str | None,
    end_date: str | None,
    adjust: str,
) -> tuple[str, str, str, str | None, str | None, str]:
    return (stock_code, market.upper(), period, start_date, end_date, adjust)


def _kline_cache_enabled(
    fetcher: Callable[..., pd.DataFrame] | None,
    fallback_fetcher: Callable[..., pd.DataFrame] | None,
) -> bool:
    return fetcher is None and fallback_fetcher is None and settings.market_kline_cache_ttl_seconds > 0


def _get_cached_kline(
    cache_key: tuple[str, str, str, str | None, str | None, str],
    *,
    allow_stale: bool = False,
) -> dict | None:
    with _KLINE_CACHE_LOCK:
        cached = _KLINE_CACHE.get(cache_key)
    if cached is not None:
        expires_at, payload = cached
        return _cached_kline_response(payload, expires_at, allow_stale=allow_stale, cache_layer="memory")

    disk_cached = _read_disk_cached_kline(cache_key)
    if disk_cached is None:
        return None
    expires_at, payload = disk_cached
    response = _cached_kline_response(payload, expires_at, allow_stale=allow_stale, cache_layer="disk")
    if response is not None:
        with _KLINE_CACHE_LOCK:
            _KLINE_CACHE[cache_key] = (expires_at, copy.deepcopy(payload))
    return response


def _cached_kline_response(
    payload: dict,
    expires_at: float,
    *,
    allow_stale: bool,
    cache_layer: str,
) -> dict | None:
    expired = expires_at <= time.time()
    if expired and not allow_stale:
        return None
    response = copy.deepcopy(payload)
    response["cached"] = True
    response["cache_status"] = "stale_if_error" if expired else "hit"
    response["cache_layer"] = cache_layer
    return response


def _set_cached_kline(cache_key: tuple[str, str, str, str | None, str | None, str], payload: dict) -> None:
    expires_at = time.time() + settings.market_kline_cache_ttl_seconds
    with _KLINE_CACHE_LOCK:
        _KLINE_CACHE[cache_key] = (expires_at, copy.deepcopy(payload))
    _write_disk_cached_kline(cache_key, expires_at, payload)


def _read_disk_cached_kline(cache_key: tuple[str, str, str, str | None, str | None, str]) -> tuple[float, dict] | None:
    cache_path = _kline_disk_cache_path(cache_key)
    if cache_path is None or not cache_path.exists():
        return None
    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if tuple(raw.get("cache_key") or ()) != cache_key:
        return None
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        return None
    try:
        expires_at = float(raw["expires_at"])
    except (KeyError, TypeError, ValueError):
        return None
    return expires_at, payload


def _write_disk_cached_kline(
    cache_key: tuple[str, str, str, str | None, str | None, str],
    expires_at: float,
    payload: dict,
) -> None:
    cache_path = _kline_disk_cache_path(cache_key)
    if cache_path is None:
        return
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "cache_key": list(cache_key),
            "expires_at": expires_at,
            "payload": payload,
            "written_at": time.time(),
        }
        temp_path = cache_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temp_path.replace(cache_path)
    except OSError:
        return


def _kline_disk_cache_path(cache_key: tuple[str, str, str, str | None, str | None, str]) -> Path | None:
    configured_dir = settings.market_kline_cache_dir.strip()
    if not configured_dir:
        return None
    cache_dir = Path(configured_dir)
    if not cache_dir.is_absolute():
        cache_dir = PROJECT_ROOT / cache_dir
    digest = hashlib.sha256(json.dumps(cache_key, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.json"
