from datetime import date, timedelta


def get_kline_mock(
    stock_code: str,
    market: str = "A",
    period: str = "daily",
    start_date: str | None = None,
    end_date: str | None = None,
    adjust: str = "qfq",
) -> dict:
    end = date.today()
    start = end - timedelta(days=14)
    prices = [
        (start + timedelta(days=index), 7.20 + index * 0.03)
        for index in range(10)
    ]
    kline_data = [
        {
            "date": day.isoformat(),
            "open": round(price, 2),
            "close": round(price + 0.05, 2),
            "high": round(price + 0.12, 2),
            "low": round(price - 0.08, 2),
            "volume": 10000000 + index * 120000,
            "amount": round((10000000 + index * 120000) * (price + 0.05), 2),
        }
        for index, (day, price) in enumerate(prices)
    ]

    return {
        "stock_code": stock_code,
        "market": market,
        "display_code": f"{stock_code}.SH" if market == "A" and stock_code.startswith("6") else stock_code,
        "company_name": "示例上市公司",
        "period": period,
        "adjust": adjust,
        "cached": True,
        "data_source": "mock",
        "start_date": start_date,
        "end_date": end_date,
        "kline_data": kline_data,
        "events": [
            {
                "date": kline_data[4]["date"],
                "type": "融资",
                "label": "图谱事件标注示例",
                "source_node_id": "event_demo",
                "source_text": "示例上市公司披露重大融资事件。",
            }
        ],
    }
