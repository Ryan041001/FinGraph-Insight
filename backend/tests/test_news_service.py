from app.services.news_service import search_news_events


class FakeGateway:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = []

    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        self.calls.append({"task": task, "messages": messages})
        return self.content


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
