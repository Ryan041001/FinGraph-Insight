import pandas as pd

from app.services.market_service import build_kline_response, normalize_kline_frame


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
    assert response["kline_data"][0]["date"] == "2024-03-15"
