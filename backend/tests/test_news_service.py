from app.services.news_service import search_news_events


class FakeGateway:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = []

    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        self.calls.append({"task": task, "messages": messages})
        return self.content


class FailingGateway:
    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        raise RuntimeError("LLM response missing choices.")


def test_search_news_events_parses_structured_events():
    gateway = FakeGateway(
        """
        {
          "events": [
            {
              "event_type": "litigation",
              "sentiment": "negative",
              "title": "示例公司涉及诉讼",
              "date": "2024-03-15",
              "source_url": "https://example.com/news",
              "evidence": "公告披露涉及诉讼"
            }
          ]
        }
        """
    )

    events = search_news_events("示例公司", gateway)

    assert events[0]["event_type"] == "litigation"
    assert events[0]["source_url"] == "https://example.com/news"
    assert gateway.calls[0]["task"] == "news_search"


def test_search_news_events_falls_back_when_events_shape_is_invalid():
    gateway = FakeGateway('{"events":{"title":"示例公司涉及诉讼"}}')

    events = search_news_events("示例公司", gateway)

    assert events[0]["title"] == "企业线索待核验"
    assert events[0]["event_type"] == "public_info"


def test_search_news_events_returns_public_clue_when_llm_routes_fail():
    events = search_news_events("宇树科技", FailingGateway())

    assert events == [
        {
            "event_type": "public_info",
            "sentiment": "unknown",
            "title": "企业线索待核验",
            "date": "未知",
            "source_url": "",
            "evidence": "宇树科技 暂未获取到可直接核验的证据线索，已保留企业名称并等待后续补充。",
        }
    ]
