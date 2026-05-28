from datetime import date, datetime, timedelta, timezone
from collections.abc import Callable

import httpx
import pandas as pd


class MarketDataError(RuntimeError):
    pass


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
    fetchers: list[tuple[str, Callable[..., pd.DataFrame]]] = [("akshare", fetcher or fetch_akshare_kline)]
    if fallback_fetcher is not None:
        fetchers.append(("yahoo_chart", fallback_fetcher))
    elif fetcher is None:
        fetchers.append(("yahoo_chart", fetch_yahoo_kline))

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
            return _kline_payload(
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
