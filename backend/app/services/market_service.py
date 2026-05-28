from datetime import date, timedelta
from collections.abc import Callable

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
) -> dict:
    resolved_fetcher = fetcher or fetch_akshare_kline
    try:
        frame = resolved_fetcher(
            stock_code=stock_code,
            market=market,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
    except Exception as exc:
        raise MarketDataError(str(exc)) from exc

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
        data_source="akshare",
    )


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
