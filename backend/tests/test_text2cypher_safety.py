import pytest

from app.services.text2cypher_service import sanitize_readonly_cypher


def test_sanitize_readonly_cypher_appends_default_limit():
    cypher, rules = sanitize_readonly_cypher("MATCH (c:Company) RETURN c")

    assert cypher == "MATCH (c:Company) RETURN c LIMIT 50"
    assert "limit_added" in rules


def test_sanitize_readonly_cypher_caps_large_limit():
    cypher, rules = sanitize_readonly_cypher("MATCH (c:Company) RETURN c LIMIT 500")

    assert cypher == "MATCH (c:Company) RETURN c LIMIT 100"
    assert "limit_capped" in rules


def test_sanitize_readonly_cypher_removes_comments_before_keyword_scan():
    with pytest.raises(ValueError, match="DELETE"):
        sanitize_readonly_cypher("MATCH (c) RETURN c // harmless\nDELETE c")


def test_sanitize_readonly_cypher_rejects_deep_variable_paths():
    with pytest.raises(ValueError, match="路径深度"):
        sanitize_readonly_cypher("MATCH p=(a)-[*1..5]-(b) RETURN p LIMIT 50")
