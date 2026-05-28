from __future__ import annotations

from typing import Any

import pandas as pd


class AkshareFetchError(RuntimeError):
    pass


def fetch_akshare_news(symbol: str = "600000") -> list[dict[str, str]]:
    try:
        import akshare as ak

        fetch = getattr(ak, "stock_news_em")
        frame = fetch(symbol=symbol)
        return normalize_news_frame(frame)
    except Exception as exc:
        raise AkshareFetchError(str(exc)) from exc


def normalize_news_frame(frame: pd.DataFrame) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for _, row in frame.fillna("").iterrows():
        records.append(
            {
                "title": _field(row, "新闻标题", "标题", "title"),
                "content": _field(row, "新闻内容", "内容", "content"),
                "source": _field(row, "文章来源", "来源", "source"),
                "pub_date": _field(row, "发布时间", "日期", "pub_date", "date"),
            }
        )
    return records


def _field(row: Any, *names: str) -> str:
    for name in names:
        if name in row and str(row[name]).strip():
            return str(row[name]).strip()
    return ""
