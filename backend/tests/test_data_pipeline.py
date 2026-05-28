import json

from app.data.financial_dataset_loader import (
    load_financial_dataset_directory,
    load_financial_table,
    load_graph_payload_from_json,
)
from app.data.text_preprocessor import chunk_text, clean_text
from app.services.entity_resolution_service import EntityResolver, normalize_entity_name


def test_clean_text_removes_html_and_collapses_whitespace():
    raw_text = "<p>红杉资本&nbsp; 领投了<br>示例科技B轮融资。</p>"

    assert clean_text(raw_text) == "红杉资本 领投了 示例科技B轮融资。"


def test_chunk_text_prefers_sentence_boundaries():
    text = "第一句介绍公司。第二句介绍投资方。第三句介绍融资。"

    chunks = chunk_text(text, max_chars=16, overlap_chars=0)

    assert chunks == ["第一句介绍公司。", "第二句介绍投资方。", "第三句介绍融资。"]


def test_normalize_entity_name_removes_common_company_noise():
    assert normalize_entity_name(" 示例科技（杭州）有限公司 ") == "示例科技杭州"
    assert normalize_entity_name("ＡＢＣ资本") == "ABC资本"


def test_entity_resolver_matches_alias_and_returns_stable_id():
    resolver = EntityResolver(
        aliases={
            "蚂蚁金服": "蚂蚁科技集团股份有限公司",
            "AntGroup": "蚂蚁科技集团股份有限公司",
        }
    )

    result = resolver.resolve("蚂蚁金服", entity_type="Company")

    assert result["resolved_name"] == "蚂蚁科技集团股份有限公司"
    assert result["match_type"] == "alias"
    assert result["confidence"] == 0.95
    assert result["resolved_id"].startswith("company_")


def test_load_graph_payload_from_json(tmp_path):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "company_demo",
                        "label": "示例科技",
                        "type": "Company",
                        "properties": {"industry": "金融科技"},
                        "risk_level": "normal",
                    }
                ],
                "edges": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    graph = load_graph_payload_from_json(graph_path)

    assert graph.nodes[0].id == "company_demo"
    assert graph.nodes[0].properties["industry"] == "金融科技"


def test_load_financial_table_maps_investment_rows_to_graph(tmp_path):
    table_path = tmp_path / "funding.csv"
    table_path.write_text(
        "企业名称,投资方,轮次,金额,日期\n星河数据,红杉资本,B轮,3000万元,2024-03-15\n",
        encoding="utf-8",
    )

    graph = load_financial_table(table_path)

    node_labels = {node.label for node in graph.nodes}
    edge_types = {edge.type for edge in graph.edges}

    assert {"星河数据", "红杉资本", "星河数据B轮融资事件"}.issubset(node_labels)
    assert {"INVESTED_IN", "RECEIVED_FUNDING"}.issubset(edge_types)
    assert all(edge.provenance["source"] == "funding.csv" for edge in graph.edges)


def test_load_financial_dataset_directory_merges_supported_files(tmp_path):
    (tmp_path / "funding.csv").write_text(
        "企业名称,投资方,轮次\n星河数据,红杉资本,B轮\n",
        encoding="utf-8",
    )
    (tmp_path / "ignore.txt").write_text("ignored", encoding="utf-8")

    graph = load_financial_dataset_directory(tmp_path)

    assert any(node.label == "星河数据" for node in graph.nodes)
    assert any(edge.type == "INVESTED_IN" for edge in graph.edges)
