import pytest

from app.services.extraction_service import (
    judge_extraction_with_llm,
    extract_with_llm,
    refine_extraction_with_llm,
)
from app.services.graph_rag_service import answer_with_llm_graph_context
from app.services.self_refine_service import extract_with_self_refine
from app.services.text2cypher_service import generate_cypher_with_llm
from tests.graph_fixtures import funding_graph
from tests.test_api_contract import client


class FakeGateway:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = []

    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        self.calls.append(
            {
                "task": task,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self.content


class SequenceGateway:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls = []

    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        self.calls.append(
            {
                "task": task,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self.contents.pop(0)


def test_extract_with_self_refine_stops_when_critique_has_no_issues():
    gateway = SequenceGateway(
        [
            '{"entities":[{"name":"星河数据","type":"Company","evidence":"星河数据完成融资"}],'
            '"relationships":[],"warnings":[]}',
            '{"issues":[]}',
        ]
    )

    payload = extract_with_self_refine("星河数据完成融资。", gateway, max_iterations=2)

    assert payload["entities"][0]["name"] == "星河数据"
    assert len(gateway.calls) == 2
    assert gateway.calls[1]["task"] == "extraction"


def test_extract_with_self_refine_refines_when_critique_reports_issues():
    gateway = SequenceGateway(
        [
            '{"entities":[{"name":"星河数据","type":"Company","evidence":"星河数据完成融资"}],'
            '"relationships":[],"warnings":[]}',
            '{"issues":[{"type":"missing_relation","description":"遗漏红杉资本领投关系"}]}',
            '{"entities":[{"name":"星河数据","type":"Company","evidence":"星河数据完成融资"},'
            '{"name":"红杉资本","type":"Institution","evidence":"红杉资本领投"}],'
            '"relationships":[{"head":"红杉资本","relation":"INVESTED_IN","tail":"星河数据",'
            '"evidence":"红杉资本领投星河数据融资","confidence":0.91}],"warnings":[]}',
            '{"issues":[]}',
        ]
    )

    payload = extract_with_self_refine("星河数据完成融资，红杉资本领投。", gateway, max_iterations=1)

    assert len(gateway.calls) == 3
    assert payload["relationships"][0]["relation"] == "INVESTED_IN"
    assert payload["relationships"][0]["status"] == "confirmed"


def test_extract_with_llm_parses_structured_json():
    gateway = FakeGateway(
        """
        {
          "entities": [
            {"name": "星河数据", "type": "Company", "evidence": "星河数据完成B轮融资"},
            {"name": "红杉资本", "type": "Institution", "evidence": "红杉资本领投"},
            {"name": "B轮融资", "type": "Event", "evidence": "B轮融资"}
          ],
          "relationships": [
            {
              "head": "红杉资本",
              "relation": "INVESTED_IN",
              "tail": "B轮融资",
              "attributes": {"role": "领投", "round": "B轮"},
              "evidence": "星河数据完成B轮融资，红杉资本领投。",
              "confidence": 0.93
            }
          ],
          "warnings": []
        }
        """
    )

    payload = extract_with_llm("星河数据完成B轮融资，红杉资本领投。", gateway)

    assert payload["entities"][0]["name"] == "星河数据"
    assert payload["relationships"][0]["relation"] == "INVESTED_IN"
    assert payload["relationships"][0]["status"] == "confirmed"
    assert gateway.calls[0]["task"] == "extraction"


def test_extract_with_llm_drops_dangling_relationship_and_warns():
    gateway = FakeGateway(
        """
        {
          "entities": [
            {"name": "星河数据", "type": "Company"},
            {"name": "红杉资本", "type": "Institution"}
          ],
          "relationships": [
            {"head": "红杉资本", "relation": "INVESTED_IN", "tail": "星河数据", "confidence": 0.9},
            {"head": "红杉资本", "relation": "INVESTED_IN", "tail": "幽灵实体", "confidence": 0.9}
          ],
          "warnings": []
        }
        """
    )

    payload = extract_with_llm("星河数据融资", gateway)

    # Only the relationship whose endpoints both resolve survives.
    assert len(payload["relationships"]) == 1
    rel = payload["relationships"][0]
    assert rel["head_temp_id"] and rel["tail_temp_id"]
    # The dropped one surfaces as a warning rather than a dangling edge.
    assert any("幽灵实体" in w for w in payload["warnings"])


def test_extract_with_llm_accepts_common_endpoint_aliases():
    gateway = FakeGateway(
        """
        {
          "entities": [
            {"name": "云链智能科技有限公司", "type": "Company"},
            {"name": "国投创业", "type": "Institution"},
            {"name": "B轮融资", "type": "Event"}
          ],
          "relationships": [
            {"source": "国投创业", "type": "领投", "target": "B轮融资", "confidence": 0.91},
            {"head_entity": {"name": "云链智能科技有限公司"}, "relation": "获得融资", "tail_entity": {"name": "B轮融资"}, "confidence": 0.91}
          ],
          "warnings": []
        }
        """
    )

    payload = extract_with_llm("云链智能科技有限公司完成B轮融资，国投创业领投。", gateway)

    assert [relationship["relation"] for relationship in payload["relationships"]] == [
        "INVESTED_IN",
        "RECEIVED_FUNDING",
    ]
    assert payload["warnings"] == []


def test_extract_with_llm_duplicate_entity_name_keeps_first_temp_id():
    gateway = FakeGateway(
        """
        {
          "entities": [
            {"name": "同名公司", "type": "Company"},
            {"name": "同名公司", "type": "Company"},
            {"name": "投资方X", "type": "Institution"}
          ],
          "relationships": [
            {"head": "投资方X", "relation": "INVESTED_IN", "tail": "同名公司", "confidence": 0.9}
          ],
          "warnings": []
        }
        """
    )

    payload = extract_with_llm("同名公司融资", gateway)

    first_company_temp = next(e["temp_id"] for e in payload["entities"] if e["name"] == "同名公司")
    assert payload["relationships"][0]["tail_temp_id"] == first_company_temp


def test_extract_with_llm_recovers_json_from_fenced_response():
    gateway = FakeGateway(
        """
        ```json
        {
          "entities": [
            {"name": "星河数据", "type": "Company", "evidence": "星河数据完成B轮融资"}
          ],
          "relationships": [],
          "warnings": []
        }
        ```
        """
    )

    payload = extract_with_llm("星河数据完成B轮融资。", gateway)

    assert payload["entities"][0]["name"] == "星河数据"
    assert payload["relationships"] == []


def test_extract_with_llm_rejects_non_list_entities():
    gateway = FakeGateway('{"entities":{"name":"星河数据"},"relationships":[],"warnings":[]}')

    with pytest.raises(ValueError, match="entities"):
        extract_with_llm("星河数据完成B轮融资。", gateway)


def test_judge_extraction_with_llm_updates_confidence_and_status():
    payload = {
        "document": {"content_hash": "doc_1"},
        "entities": [],
        "relationships": [
            {
                "temp_id": "r1",
                "relation": "INVESTED_IN",
                "evidence": "红杉资本领投。",
                "confidence": 0.6,
                "status": "pending_review",
            }
        ],
        "warnings": [],
    }
    gateway = FakeGateway('{"judgements":[{"temp_id":"r1","confidence":0.94,"reason":"原文明确支持"}]}')

    judged = judge_extraction_with_llm(payload, gateway)

    assert judged["relationships"][0]["confidence"] == 0.94
    assert judged["relationships"][0]["status"] == "confirmed"
    assert judged["relationships"][0]["judge_reason"] == "原文明确支持"
    assert gateway.calls[0]["task"] == "judge"


def test_refine_extraction_with_llm_normalizes_refined_payload():
    initial_payload = {
        "document": {"content_hash": "doc_1"},
        "entities": [
            {"temp_id": "e1", "name": "星河数据", "type": "Company"},
        ],
        "relationships": [],
        "warnings": ["missing_investor"],
    }
    gateway = FakeGateway(
        """
        {
          "entities": [
            {"name": "星河数据", "type": "Company", "evidence": "星河数据完成B轮融资"},
            {"name": "红杉资本", "type": "Institution", "evidence": "红杉资本领投"},
            {"name": "B轮融资", "type": "Event", "evidence": "B轮融资"}
          ],
          "relationships": [
            {
              "head": "红杉资本",
              "relation": "INVESTED_IN",
              "tail": "B轮融资",
              "attributes": {"role": "领投"},
              "evidence": "星河数据完成B轮融资，红杉资本领投。",
              "confidence": 0.9
            }
          ],
          "warnings": []
        }
        """
    )

    refined = refine_extraction_with_llm("星河数据完成B轮融资，红杉资本领投。", initial_payload, gateway)

    assert len(refined["entities"]) == 3
    assert refined["relationships"][0]["relation"] == "INVESTED_IN"
    assert refined["relationships"][0]["status"] == "confirmed"
    assert gateway.calls[0]["task"] == "extraction"


def test_generate_cypher_with_llm_sanitizes_model_output():
    gateway = FakeGateway('{"cypher": "MATCH (c:Company) RETURN c"}')

    cypher, rules = generate_cypher_with_llm("查询所有公司", gateway)

    assert cypher == "MATCH (c:Company) RETURN c LIMIT 50"
    assert "limit_added" in rules
    assert gateway.calls[0]["task"] == "text2cypher"


def test_generate_cypher_with_llm_recovers_json_from_prefixed_response():
    gateway = FakeGateway(
        '可以，结果如下：\n```json\n{"cypher": "MATCH (c:Company) RETURN c"}\n```'
    )

    cypher, rules = generate_cypher_with_llm("查询所有公司", gateway)

    assert cypher == "MATCH (c:Company) RETURN c LIMIT 50"
    assert "limit_added" in rules


def test_generate_cypher_with_llm_requires_cypher_string():
    gateway = FakeGateway('{"query":"MATCH (c:Company) RETURN c"}')

    with pytest.raises(ValueError, match="cypher"):
        generate_cypher_with_llm("查询所有公司", gateway)


def test_generate_cypher_with_llm_allows_runtime_schema_tokens(monkeypatch):
    class RuntimeSchemaStore:
        def schema_tokens(self):
            return {"Dataset"}, {"MENTIONS"}

    monkeypatch.setattr("app.services.text2cypher_service.graph_store", RuntimeSchemaStore())
    gateway = FakeGateway('{"cypher":"MATCH (d:Dataset)-[:MENTIONS]->(c:Company) RETURN d, c"}')

    cypher, rules = generate_cypher_with_llm("查询数据集提及的公司", gateway)

    assert cypher == "MATCH (d:Dataset)-[:MENTIONS]->(c:Company) RETURN d, c LIMIT 50"
    assert "schema_checked" in rules


def test_extract_route_uses_configured_llm_when_enabled(monkeypatch):
    gateway = FakeGateway(
        '{"entities":[{"name":"天河科技","type":"Company","evidence":"天河科技完成A轮融资"}],'
        '"relationships":[],"warnings":[]}'
    )

    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: gateway)

    response = client.post("/extract", json={"text": "天河科技完成A轮融资。", "options": {"judge": False}})

    assert response.status_code == 200
    assert response.json()["entities"][0]["name"] == "天河科技"


def test_extract_route_applies_self_refine_when_enabled(monkeypatch):
    gateway = SequenceGateway(
        [
            '{"entities":[{"name":"星河数据","type":"Company","evidence":"星河数据完成融资"}],'
            '"relationships":[],"warnings":["missing_investor"]}',
            '{"issues":[{"type":"missing_relation","description":"遗漏投资方"}]}',
            '{"entities":[{"name":"星河数据","type":"Company","evidence":"星河数据完成融资"},'
            '{"name":"红杉资本","type":"Institution","evidence":"红杉资本领投"}],'
            '"relationships":[{"head":"红杉资本","relation":"INVESTED_IN","tail":"星河数据",'
            '"evidence":"红杉资本领投星河数据融资","confidence":0.91}],"warnings":[]}',
            '{"issues":[]}',
        ]
    )

    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: gateway)

    response = client.post(
        "/extract",
        json={
            "text": "星河数据完成融资，红杉资本领投。",
            "options": {"self_refine": True, "judge": False},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(gateway.calls) == 4
    assert payload["relationships"][0]["relation"] == "INVESTED_IN"
    assert payload["warnings"] == []


def test_text2cypher_route_uses_configured_llm_when_enabled(monkeypatch):
    gateway = FakeGateway('{"cypher":"MATCH (c:Company) RETURN c"}')

    monkeypatch.setattr("app.main.HttpLLMGateway", lambda: gateway)

    response = client.post("/qa/text2cypher", json={"question": "查询所有公司"})

    assert response.status_code == 200
    assert response.json()["cypher"] == "MATCH (c:Company) RETURN c LIMIT 50"


def test_answer_with_llm_graph_context_preserves_graph_and_citations():
    gateway = FakeGateway('{"answer":"根据图谱，星河数据获得B轮融资。"}')
    graph = funding_graph("星河数据")

    response = answer_with_llm_graph_context("星河数据融资情况？", graph, gateway)

    assert response["answer"] == "根据图谱，星河数据获得B轮融资。"
    assert response["supporting_graph"]["nodes"]
    assert response["citations"]
    assert gateway.calls[0]["task"] == "graph_rag"


def test_answer_with_llm_graph_context_requires_answer_string():
    gateway = FakeGateway('{"result":"根据图谱回答"}')
    graph = funding_graph("星河数据")

    with pytest.raises(ValueError, match="answer"):
        answer_with_llm_graph_context("星河数据融资情况？", graph, gateway)
