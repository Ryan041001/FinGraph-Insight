from app.services.entity_resolution_service import EntityResolver, normalize_entity_name
from app.services.extraction_service import extract_with_deepseek


class FakeGateway:
    def complete(self, *, task, messages, temperature=0.2, max_tokens=None):
        return """
        {
          "entities": [
            {"name": "星河数据有限公司", "type": "Company", "evidence": "星河数据有限公司完成融资"},
            {"name": "红杉中国", "type": "Institution", "evidence": "红杉中国领投"},
            {"name": "B轮融资", "type": "Event", "evidence": "B轮融资"}
          ],
          "relationships": [
            {
              "head": "红杉中国",
              "relation": "INVESTED_IN",
              "tail": "B轮融资",
              "attributes": {"role": "领投"},
              "evidence": "星河数据有限公司完成B轮融资，红杉中国领投。",
              "confidence": 0.92
            }
          ],
          "warnings": []
        }
        """


def test_entity_resolver_supports_exact_normalized_alias_and_fuzzy_matches():
    resolver = EntityResolver(
        aliases={"红杉中国": "红杉资本中国基金"},
        candidates=[
            {"name": "星河数据", "type": "Company"},
            {"name": "红杉资本中国基金", "type": "Institution"},
        ],
    )

    exact = resolver.resolve("星河数据", "Company")
    normalized = resolver.resolve("星河数据有限公司", "Company")
    alias = resolver.resolve("红杉中国", "Institution")
    fuzzy = resolver.resolve("星河数剧", "Company")

    assert exact["match_type"] == "exact"
    assert exact["resolved_name"] == "星河数据"
    assert exact["confidence"] == 1.0

    assert normalized["match_type"] == "normalized"
    assert normalized["resolved_name"] == "星河数据"
    assert normalized["confidence"] >= 0.9

    assert alias["match_type"] == "alias"
    assert alias["resolved_name"] == "红杉资本中国基金"
    assert alias["confidence"] == 0.95

    assert fuzzy["match_type"] == "fuzzy"
    assert fuzzy["resolved_name"] == "星河数据"
    assert fuzzy["confidence"] >= 0.7
    assert fuzzy["candidates"][0]["name"] == "星河数据"


def test_extract_with_deepseek_uses_entity_resolver_for_resolved_ids(monkeypatch):
    resolver = EntityResolver(
        aliases={"红杉中国": "红杉资本中国基金"},
        candidates=[
            {"name": "星河数据", "type": "Company"},
            {"name": "红杉资本中国基金", "type": "Institution"},
        ],
    )
    monkeypatch.setattr("app.services.extraction_service.entity_resolver", resolver)

    payload = extract_with_deepseek("星河数据有限公司完成B轮融资，红杉中国领投。", FakeGateway())

    by_name = {entity["name"]: entity for entity in payload["entities"]}

    assert by_name["星河数据有限公司"]["resolved_name"] == "星河数据"
    assert by_name["星河数据有限公司"]["resolution_match_type"] == "normalized"
    assert by_name["红杉中国"]["resolved_name"] == "红杉资本中国基金"
    assert by_name["红杉中国"]["resolution_match_type"] == "alias"
    assert by_name["星河数据有限公司"]["resolved_id"].startswith("company_")
    assert normalize_entity_name("星河数据有限公司") == "星河数据"
