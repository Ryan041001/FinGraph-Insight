import json

from app.data.financial_dataset_loader import (
    _split_investors,
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


def test_load_business_registry_table_creates_company_only(tmp_path):
    table_path = tmp_path / "SmoothNLP工商数据集样本10K.csv"
    table_path.write_text(
        (
            "名称,公司名称,公司介绍,工商,地址,工商注册id,成立时间,法人代表,注册资金,统一信用代码,网址\n"
            "铁大大,宁波西铁供应链管理有限公司,中欧铁路物流服务提供商,宁波西铁供应链管理有限公司,"
            "宁波鄞州区百丈路158号,330214000048633,2014-03-12,邵一峰,500万元人民币,"
            "913302040933533733,www.tiedada.com\n"
        ),
        encoding="utf-8",
    )

    graph = load_financial_table(table_path)

    assert len(graph.nodes) == 1
    assert graph.nodes[0].type == "Company"
    assert graph.nodes[0].label == "宁波西铁供应链管理有限公司"
    assert graph.nodes[0].properties["short_name"] == "铁大大"
    assert graph.nodes[0].properties["legal_representative"] == "邵一峰"
    assert graph.nodes[0].properties["credit_code"] == "913302040933533733"
    assert graph.edges == []


def test_split_investors_preserves_english_names_and_splits_on_separators():
    # CJK punctuation separates investors; spaces inside an English firm name must survive.
    assert _split_investors("IDG资本、GGV Capital") == ["IDG资本", "GGV Capital"]
    assert _split_investors("红杉资本，IDG资本；经纬中国") == ["红杉资本", "IDG资本", "经纬中国"]
    # Pure-CJK space-separated names still split (legacy SmoothNLP format).
    assert _split_investors("鼎珮投资集团 国投创业 君联资本") == ["鼎珮投资集团", "国投创业", "君联资本"]
    # A single English name with spaces stays as one investor.
    assert _split_investors("Sequoia Capital") == ["Sequoia Capital"]
    assert _split_investors("GGV Capital") == ["GGV Capital"]
    assert _split_investors("") == []


def test_load_real_investment_event_table_uses_financing_company_and_split_investors(tmp_path):
    table_path = tmp_path / "SmoothNLP投资事件数据集样本2k.csv"
    table_path.write_text(
        (
            "事件资讯,投资方,融资方,融资时间,轮次,金额\n"
            "邦盛科技C轮获得等3.5亿人民币投资,鼎珮投资集团 国投创业 君联资本 新湖投资,"
            "邦盛科技,2019-06-03,C轮,3.5亿人民币\n"
        ),
        encoding="utf-8",
    )

    graph = load_financial_table(table_path)

    labels_by_type = {}
    for node in graph.nodes:
        labels_by_type.setdefault(node.type, set()).add(node.label)
    edge_types = [edge.type for edge in graph.edges]

    assert labels_by_type["Company"] == {"邦盛科技"}
    assert {"鼎珮投资集团", "国投创业", "君联资本", "新湖投资"}.issubset(labels_by_type["Institution"])
    assert labels_by_type["Event"] == {"邦盛科技C轮融资事件"}
    assert edge_types.count("RECEIVED_FUNDING") == 1
    assert edge_types.count("INVESTED_IN") == 4
    assert all("邦盛科技C轮获得等3.5亿人民币投资" in edge.provenance["source_text"] for edge in graph.edges)


def test_load_investment_institution_table_creates_institution_only(tmp_path):
    table_path = tmp_path / "SmoothNLP投资结构数据集样本1k.csv"
    table_path.write_text(
        "机构名称,介绍,行业,规模,轮次\nLe Peigné,,房产1家,,B轮1家\n",
        encoding="utf-8",
    )

    graph = load_financial_table(table_path)

    assert len(graph.nodes) == 1
    assert graph.nodes[0].type == "Institution"
    assert graph.nodes[0].label == "Le Peigné"
    assert graph.nodes[0].properties["industry_preference"] == "房产1家"
    assert graph.nodes[0].properties["investment_stage"] == "B轮1家"
    assert graph.edges == []


def test_load_news_table_creates_document_nodes_without_relationships(tmp_path):
    table_path = tmp_path / "SmoothNLP36kr新闻数据集10k.csv"
    table_path.write_text(
        (
            "content,insert_ts,pub_ts,title,url\n"
            "这是一条真实新闻正文,2019-06-12 09:31:40,2012-04-16 00:00:00,"
            "革命之路：从产品到盈利,https://36kr.com/p/100347\n"
        ),
        encoding="utf-8",
    )

    graph = load_financial_table(table_path)

    assert len(graph.nodes) == 1
    assert graph.nodes[0].type == "Document"
    assert graph.nodes[0].label == "革命之路：从产品到盈利"
    assert graph.nodes[0].properties["source"] == "SmoothNLP36kr新闻数据集10k.csv"
    assert graph.nodes[0].properties["url"] == "https://36kr.com/p/100347"
    assert graph.edges == []


def test_load_financial_dataset_directory_merges_supported_files(tmp_path):
    (tmp_path / "funding.csv").write_text(
        "企业名称,投资方,轮次\n星河数据,红杉资本,B轮\n",
        encoding="utf-8",
    )
    (tmp_path / "ignore.txt").write_text("ignored", encoding="utf-8")

    graph = load_financial_dataset_directory(tmp_path)

    assert any(node.label == "星河数据" for node in graph.nodes)
    assert any(edge.type == "INVESTED_IN" for edge in graph.edges)
