import sys
import types

import pandas as pd
import pytest

import app.services.market_service as market_service
from app.services.market_service import (
    MarketDataError,
    build_kline_response,
    fetch_yahoo_kline,
    normalize_kline_frame,
)


@pytest.fixture(autouse=True)
def clear_kline_cache():
    market_service._KLINE_CACHE.clear()
    yield
    market_service._KLINE_CACHE.clear()


def test_normalize_kline_frame_maps_akshare_columns():
    frame = pd.DataFrame(
        [
            {
                "日期": "2024-03-15",
                "开盘": 7.23,
                "收盘": 7.45,
                "最高": 7.50,
                "最低": 7.18,
                "成交量": 123,
                "成交额": 456.7,
            }
        ]
    )

    points = normalize_kline_frame(frame)

    assert points == [
        {
            "date": "2024-03-15",
            "open": 7.23,
            "close": 7.45,
            "high": 7.5,
            "low": 7.18,
            "volume": 123,
            "amount": 456.7,
        }
    ]


def test_build_kline_response_uses_fetcher_data():
    def fake_fetcher(**kwargs):
        return pd.DataFrame(
            [
                {
                    "日期": "2024-03-15",
                    "开盘": 7.23,
                    "收盘": 7.45,
                    "最高": 7.50,
                    "最低": 7.18,
                    "成交量": 123,
                    "成交额": 456.7,
                }
            ]
        )

    response = build_kline_response("600000", fetcher=fake_fetcher)

    assert response["data_source"] == "akshare"
    assert response["cached"] is False
    assert response["company_name"] == "600000"
    assert response["kline_data"][0]["date"] == "2024-03-15"
    assert response["events"] == []


def test_build_kline_response_uses_yfinance_as_default_primary_source(monkeypatch):
    def yfinance_fetcher(**kwargs):
        return pd.DataFrame(
            [
                {
                    "date": "2024-01-02",
                    "open": 7.20,
                    "close": 7.30,
                    "high": 7.35,
                    "low": 7.10,
                    "volume": 1000,
                    "amount": 0,
                }
            ]
        )

    def akshare_fetcher(**kwargs):
        return pd.DataFrame(
            [
                {
                    "日期": "2024-03-15",
                    "开盘": 7.23,
                    "收盘": 7.45,
                    "最高": 7.50,
                    "最低": 7.18,
                    "成交量": 123,
                    "成交额": 456.7,
                }
            ]
        )

    monkeypatch.setattr(market_service, "fetch_yfinance_kline", yfinance_fetcher, raising=False)
    monkeypatch.setattr(market_service, "fetch_akshare_kline", akshare_fetcher)
    monkeypatch.setattr(market_service, "fetch_yahoo_kline", lambda **kwargs: pd.DataFrame([]))

    response = build_kline_response("600000")

    assert response["data_source"] == "yfinance"
    assert response["kline_data"][0]["date"] == "2024-01-02"


def test_build_kline_response_raises_instead_of_returning_mock_when_fetcher_fails():
    def failing_fetcher(**kwargs):
        raise RuntimeError("akshare unavailable")

    with pytest.raises(MarketDataError, match="akshare unavailable"):
        build_kline_response("600000", fetcher=failing_fetcher)


def test_build_kline_response_raises_when_fetcher_returns_no_rows():
    def empty_fetcher(**kwargs):
        return pd.DataFrame([])

    with pytest.raises(MarketDataError, match="No market data"):
        build_kline_response("600000", fetcher=empty_fetcher)


def test_build_kline_response_falls_back_to_yahoo_chart_when_akshare_fails():
    def failing_fetcher(**kwargs):
        raise RuntimeError("akshare unavailable")

    def yahoo_fetcher(**kwargs):
        return pd.DataFrame(
            [
                {
                    "date": "2024-01-02",
                    "open": 7.20,
                    "close": 7.30,
                    "high": 7.35,
                    "low": 7.10,
                    "volume": 1000,
                    "amount": 0,
                }
            ]
        )

    response = build_kline_response("600000", fetcher=failing_fetcher, fallback_fetcher=yahoo_fetcher)

    assert response["data_source"] == "yahoo_chart"
    assert response["kline_data"][0]["date"] == "2024-01-02"


def test_build_kline_response_falls_back_to_yahoo_chart_when_yfinance_fails(monkeypatch):
    def failing_yfinance(**kwargs):
        raise RuntimeError("yfinance unavailable")

    def yahoo_fetcher(**kwargs):
        return pd.DataFrame(
            [
                {
                    "date": "2024-01-02",
                    "open": 7.20,
                    "close": 7.30,
                    "high": 7.35,
                    "low": 7.10,
                    "volume": 1000,
                    "amount": 0,
                }
            ]
        )

    monkeypatch.setattr(market_service, "fetch_yfinance_kline", failing_yfinance, raising=False)
    monkeypatch.setattr(market_service, "fetch_yahoo_kline", yahoo_fetcher)
    monkeypatch.setattr(market_service, "fetch_akshare_kline", lambda **kwargs: pd.DataFrame([]))

    response = build_kline_response("600000")

    assert response["data_source"] == "yahoo_chart"
    assert response["kline_data"][0]["close"] == 7.3


def test_build_kline_response_caches_default_live_fetchers(monkeypatch):
    calls = []

    def yfinance_fetcher(**kwargs):
        calls.append(kwargs["stock_code"])
        return pd.DataFrame(
            [
                {
                    "date": "2024-01-02",
                    "open": 7.20,
                    "close": 7.30,
                    "high": 7.35,
                    "low": 7.10,
                    "volume": 1000,
                    "amount": 0,
                }
            ]
        )

    monkeypatch.setattr(market_service, "fetch_yfinance_kline", yfinance_fetcher)
    monkeypatch.setattr(market_service, "fetch_yahoo_kline", lambda **kwargs: pd.DataFrame([]))
    monkeypatch.setattr(market_service, "fetch_akshare_kline", lambda **kwargs: pd.DataFrame([]))

    first = build_kline_response("688888", start_date="2024-01-01", end_date="2024-01-10")
    second = build_kline_response("688888", start_date="2024-01-01", end_date="2024-01-10")

    assert calls == ["688888"]
    assert first["cached"] is False
    assert second["cached"] is True
    assert second["data_source"] == "yfinance"


def test_build_kline_response_returns_stale_cache_when_sources_fail(monkeypatch):
    current_time = 1_000.0

    def yfinance_fetcher(**kwargs):
        return pd.DataFrame(
            [
                {
                    "date": "2024-01-02",
                    "open": 7.20,
                    "close": 7.30,
                    "high": 7.35,
                    "low": 7.10,
                    "volume": 1000,
                    "amount": 0,
                }
            ]
        )

    monkeypatch.setattr(market_service.time, "time", lambda: current_time)
    monkeypatch.setattr(market_service.settings, "market_kline_cache_ttl_seconds", 1)
    monkeypatch.setattr(market_service, "fetch_yfinance_kline", yfinance_fetcher)
    monkeypatch.setattr(market_service, "fetch_yahoo_kline", lambda **kwargs: pd.DataFrame([]))
    monkeypatch.setattr(market_service, "fetch_akshare_kline", lambda **kwargs: pd.DataFrame([]))

    first = build_kline_response("688889", start_date="2024-01-01", end_date="2024-01-10")
    current_time = 2_000.0
    monkeypatch.setattr(market_service, "fetch_yfinance_kline", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))

    second = build_kline_response("688889", start_date="2024-01-01", end_date="2024-01-10")

    assert first["cached"] is False
    assert second["cached"] is True
    assert second["cache_status"] == "stale_if_error"
    assert second["data_source"] == "yfinance"
    assert second["kline_data"][0]["close"] == 7.3


def test_fetch_yfinance_kline_maps_symbol_and_normalizes_download(monkeypatch):
    captured = {}

    def fake_download(symbol, **kwargs):
        captured["symbol"] = symbol
        captured["kwargs"] = kwargs
        frame = pd.DataFrame(
            [
                {
                    "Open": 7.20,
                    "Close": 7.30,
                    "High": 7.35,
                    "Low": 7.10,
                    "Volume": 1000,
                }
            ],
            index=pd.to_datetime(["2024-01-02"]),
        )
        frame.index.name = "Date"
        return frame

    fake_yfinance = types.SimpleNamespace(download=fake_download)
    monkeypatch.setitem(sys.modules, "yfinance", fake_yfinance)

    frame = market_service.fetch_yfinance_kline(
        stock_code="600000",
        market="A",
        start_date="2024-01-01",
        end_date="2024-01-10",
    )

    assert captured["symbol"] == "600000.SS"
    assert captured["kwargs"]["progress"] is False
    assert captured["kwargs"]["threads"] is False
    assert captured["kwargs"]["start"] == "2024-01-01"
    assert captured["kwargs"]["end"] == "2024-01-11"
    assert frame.iloc[0]["date"] == "2024-01-02"
    assert frame.iloc[0]["close"] == 7.3


def test_fetch_yahoo_kline_maps_a_share_symbol_and_chart_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "chart": {
                    "result": [
                        {
                            "timestamp": [1704153600],
                            "indicators": {
                                "quote": [
                                    {
                                        "open": [7.2],
                                        "close": [7.3],
                                        "high": [7.35],
                                        "low": [7.1],
                                        "volume": [1000],
                                    }
                                ]
                            },
                        }
                    ],
                    "error": None,
                }
            }

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr("app.services.market_service.httpx.get", fake_get)

    frame = fetch_yahoo_kline(stock_code="600000", market="A", start_date="2024-01-01", end_date="2024-01-10")

    assert "600000.SS" in captured["url"]
    assert captured["kwargs"]["timeout"] == 20.0
    assert frame.iloc[0]["date"] == "2024-01-02"
    assert frame.iloc[0]["close"] == 7.3
