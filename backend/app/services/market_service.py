import copy
import time
from datetime import date, datetime, timedelta, timezone
from collections.abc import Callable

import httpx
import pandas as pd

from app.config import settings


class MarketDataError(RuntimeError):
    pass


_KLINE_CACHE: dict[tuple[str, str, str, str | None, str | None, str], tuple[float, dict]] = {}


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


def _get_cached_kline(cache_key: tuple[str, str, str, str | None, str | None, str]) -> dict | None:
    cached = _KLINE_CACHE.get(cache_key)
    if cached is None:
        return None
    expires_at, payload = cached
    if expires_at <= time.time():
        _KLINE_CACHE.pop(cache_key, None)
        return None
    response = copy.deepcopy(payload)
    response["cached"] = True
    return response


def _set_cached_kline(cache_key: tuple[str, str, str, str | None, str | None, str], payload: dict) -> None:
    expires_at = time.time() + settings.market_kline_cache_ttl_seconds
    _KLINE_CACHE[cache_key] = (expires_at, copy.deepcopy(payload))
