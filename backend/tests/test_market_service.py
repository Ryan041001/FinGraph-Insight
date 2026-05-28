import pandas as pd
import pytest

from app.services.market_service import MarketDataError, build_kline_response, fetch_yahoo_kline, normalize_kline_frame


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
