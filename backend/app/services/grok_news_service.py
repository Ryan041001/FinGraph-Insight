from __future__ import annotations

import json
from typing import Any

from app.services.llm_service import LLMGateway, LLMTask


def search_news_events_with_grok(company_name: str, gateway: LLMGateway) -> list[dict[str, Any]]:
    content = gateway.complete(
        task=LLMTask.NEWS_SEARCH,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是金融消息面检索助手。请使用实时搜索能力查找公司近期新闻，"
                    "并严格输出 json：{\"events\":[{\"event_type\":\"...\",\"sentiment\":\"positive|neutral|negative|unknown\","
                    "\"title\":\"...\",\"date\":\"YYYY-MM-DD\",\"source_url\":\"...\",\"evidence\":\"...\"}]}。"
                    "不得输出买卖建议。"
                ),
            },
            {"role": "user", "content": f"检索 {company_name} 最近30天重要金融新闻、公告、诉讼、处罚或融资事件。"},
        ],
        temperature=0.1,
        max_tokens=2048,
    )
    payload = json.loads(content)
    return list(payload.get("events", []))
