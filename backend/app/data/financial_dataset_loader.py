from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from app.models.api import GraphEdge, GraphNode, GraphPayload
from app.services.graph_store import stable_id, node_id


_UNDISCLOSED_TOKENS = ("未披露", "未公开", "未透露")


def _evidence_confidence(amount: str, date: str) -> float:
    amount_text = (amount or "").strip()
    date_text = (date or "").strip()
    has_amount = bool(amount_text)
    has_date = bool(date_text)
    if has_amount and any(token in amount_text for token in _UNDISCLOSED_TOKENS):
        return 0.75
    if has_amount and has_date:
        return 1.0
    if has_amount or has_date:
        return 0.85
    return 0.7


def load_graph_payload_from_json(path: str | Path) -> GraphPayload:
    graph_path = Path(path)
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    return GraphPayload.model_validate(payload)


def load_financial_table(path: str | Path) -> GraphPayload:
    table_path = Path(path)
    if table_path.suffix.lower() in {".xlsx", ".xls"}:
        frame = pd.read_excel(table_path)
    else:
        frame = pd.read_csv(table_path)

    frame = frame.fillna("")
    columns = {str(column) for column in frame.columns}

    if _is_business_registry_table(columns):
        return _load_business_registry_table(frame, table_path)
    if _is_investment_event_table(columns):
        return _load_investment_event_table(frame, table_path)
    if _is_institution_table(columns):
        return _load_institution_table(frame, table_path)
    if _is_news_table(columns):
        return _load_news_table(frame, table_path)
    return _load_generic_investment_table(frame, table_path)


def _load_business_registry_table(frame: pd.DataFrame, table_path: Path) -> GraphPayload:
    nodes: dict[str, GraphNode] = {}

    for _, row in frame.iterrows():
        company_name = _field(row, "公司名称", "企业名称", "工商")
        if not company_name:
            continue

        company_id = node_id("Company", company_name)
        nodes[company_id] = GraphNode(
            id=company_id,
            label=company_name,
            type="Company",
            properties={
                "name": company_name,
                "full_name": company_name,
                "short_name": _field(row, "名称"),
                "description": _field(row, "公司介绍"),
                "registry_name": _field(row, "工商"),
                "address": _field(row, "地址"),
                "register_id": _field(row, "工商注册id"),
                "founded_at": _field(row, "成立时间"),
                "legal_representative": _field(row, "法人代表"),
                "registered_capital": _field(row, "注册资金"),
                "credit_code": _field(row, "统一信用代码"),
                "website": _field(row, "网址"),
                "source": table_path.name,
            },
        )

    return GraphPayload(nodes=list(nodes.values()), edges=[])


def _load_investment_event_table(frame: pd.DataFrame, table_path: Path) -> GraphPayload:
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}

    for _, row in frame.iterrows():
        company_name = _field(row, "融资方", "企业名称", "公司名称", "company", "company_name", "name")
        investor_name = _field(row, "投资方", "投资机构", "investor", "institution")
        round_name = _field(row, "轮次", "融资轮次", "round") or "融资"
        amount = _field(row, "金额", "融资金额", "amount")
        event_date = _field(row, "融资时间", "日期", "时间", "date")
        event_description = _field(row, "事件资讯", "description")

        if not company_name:
            continue

        company_id = node_id("Company", company_name)
        nodes[company_id] = GraphNode(
            id=company_id,
            label=company_name,
            type="Company",
            properties={"name": company_name},
        )

        event_name = f"{company_name}{round_name}融资事件"
        event_id = node_id("Event", event_name)
        nodes[event_id] = GraphNode(
            id=event_id,
            label=event_name,
            type="Event",
            properties={
                "name": event_name,
                "event_type": "funding",
                "round": round_name,
                "amount": amount,
                "date": event_date,
                "description": event_description,
                "source": table_path.name,
            },
        )

        received_id = f"rel_{stable_id(company_id, 'RECEIVED_FUNDING', event_id, table_path.name)}"
        evidence_score = _evidence_confidence(amount, event_date)
        edges[received_id] = GraphEdge(
            id=received_id,
            source=company_id,
            target=event_id,
            type="RECEIVED_FUNDING",
            label="获得融资",
            confidence=evidence_score,
            properties={"round": round_name, "amount": amount, "date": event_date},
            provenance={"source": table_path.name, "source_text": _row_text(row)},
        )

        if investor_name:
            for investor in _split_investors(investor_name):
                investor_id = node_id("Institution", investor)
                nodes[investor_id] = GraphNode(
                    id=investor_id,
                    label=investor,
                    type="Institution",
                    properties={"name": investor, "source": table_path.name},
                )
                invested_id = f"rel_{stable_id(investor_id, 'INVESTED_IN', event_id, table_path.name)}"
                edges[invested_id] = GraphEdge(
                    id=invested_id,
                    source=investor_id,
                    target=event_id,
                    type="INVESTED_IN",
                    label="投资",
                    confidence=evidence_score,
                    properties={"round": round_name, "amount": amount, "date": event_date},
                    provenance={"source": table_path.name, "source_text": _row_text(row)},
                )

    return GraphPayload(nodes=list(nodes.values()), edges=list(edges.values()))


def _load_institution_table(frame: pd.DataFrame, table_path: Path) -> GraphPayload:
    nodes: dict[str, GraphNode] = {}

    for _, row in frame.iterrows():
        institution_name = _field(row, "机构名称", "投资机构", "institution", "name")
        if not institution_name:
            continue

        institution_id = node_id("Institution", institution_name)
        nodes[institution_id] = GraphNode(
            id=institution_id,
            label=institution_name,
            type="Institution",
            properties={
                "name": institution_name,
                "description": _field(row, "介绍"),
                "industry_preference": _field(row, "行业"),
                "scale": _field(row, "规模"),
                "investment_stage": _field(row, "轮次"),
                "source": table_path.name,
            },
        )

    return GraphPayload(nodes=list(nodes.values()), edges=[])


def _load_news_table(frame: pd.DataFrame, table_path: Path) -> GraphPayload:
    nodes: dict[str, GraphNode] = {}

    for index, row in frame.iterrows():
        title = _field(row, "title", "标题", "新闻标题") or f"{table_path.stem}_{index}"
        content = _field(row, "content", "内容", "新闻内容")
        pub_date = _field(row, "pub_ts", "发布时间", "日期", "pub_date", "date")
        url = _field(row, "url", "链接", "source_url")
        document_id = f"document_{stable_id(table_path.name, title, pub_date, url, content[:80])}"
        nodes[document_id] = GraphNode(
            id=document_id,
            label=title,
            type="Document",
            properties={
                "title": title,
                "source": table_path.name,
                "url": url,
                "pub_date": pub_date,
                "insert_ts": _field(row, "insert_ts"),
                "content_hash": stable_id(content),
            },
        )

    return GraphPayload(nodes=list(nodes.values()), edges=[])


def _load_generic_investment_table(frame: pd.DataFrame, table_path: Path) -> GraphPayload:
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}

    for _, row in frame.iterrows():
        company_name = _field(row, "企业名称", "公司名称", "company", "company_name", "name")
        investor_name = _field(row, "投资方", "投资机构", "investor", "institution")
        round_name = _field(row, "轮次", "融资轮次", "round")
        amount = _field(row, "金额", "融资金额", "amount")
        event_date = _field(row, "日期", "时间", "date")

        if not company_name:
            continue

        company_id = node_id("Company", company_name)
        nodes[company_id] = GraphNode(
            id=company_id,
            label=company_name,
            type="Company",
            properties={"name": company_name, "source": table_path.name},
        )

        if not investor_name and not round_name and not amount and not event_date:
            continue

        resolved_round = round_name or "融资"
        event_name = f"{company_name}{resolved_round}融资事件"
        event_id = node_id("Event", event_name)
        nodes[event_id] = GraphNode(
            id=event_id,
            label=event_name,
            type="Event",
            properties={
                "name": event_name,
                "event_type": "funding",
                "round": resolved_round,
                "amount": amount,
                "date": event_date,
                "source": table_path.name,
            },
        )

        received_id = f"rel_{stable_id(company_id, 'RECEIVED_FUNDING', event_id, table_path.name)}"
        evidence_score = _evidence_confidence(amount, event_date)
        edges[received_id] = GraphEdge(
            id=received_id,
            source=company_id,
            target=event_id,
            type="RECEIVED_FUNDING",
            label="获得融资",
            confidence=evidence_score,
            properties={"round": resolved_round, "amount": amount, "date": event_date},
            provenance={"source": table_path.name, "source_text": _row_text(row)},
        )

        for investor in _split_investors(investor_name):
            investor_id = node_id("Institution", investor)
            nodes[investor_id] = GraphNode(
                id=investor_id,
                label=investor,
                type="Institution",
                properties={"name": investor, "source": table_path.name},
            )
            invested_id = f"rel_{stable_id(investor_id, 'INVESTED_IN', event_id, table_path.name)}"
            edges[invested_id] = GraphEdge(
                id=invested_id,
                source=investor_id,
                target=event_id,
                type="INVESTED_IN",
                label="投资",
                confidence=evidence_score,
                properties={"round": round_name, "amount": amount, "date": event_date},
                provenance={"source": table_path.name, "source_text": _row_text(row)},
            )

    return GraphPayload(nodes=list(nodes.values()), edges=list(edges.values()))


def load_financial_dataset_directory(path: str | Path) -> GraphPayload:
    dataset_path = Path(path)
    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}

    for table_path in sorted(dataset_path.rglob("*")):
        if table_path.suffix.lower() not in {".csv", ".xlsx", ".xls", ".json"}:
            continue
        graph = load_graph_payload_from_json(table_path) if table_path.suffix.lower() == ".json" else load_financial_table(table_path)
        nodes.update({node.id: node for node in graph.nodes})
        edges.update({edge.id: edge for edge in graph.edges})

    return GraphPayload(nodes=list(nodes.values()), edges=list(edges.values()))


def _field(row: pd.Series, *names: str) -> str:
    for name in names:
        if name in row and str(row[name]).strip():
            return str(row[name]).strip()
    return ""


def _row_text(row: pd.Series) -> str:
    return "；".join(f"{key}={value}" for key, value in row.items() if str(value).strip())


def _is_business_registry_table(columns: set[str]) -> bool:
    return bool({"公司名称", "统一信用代码"} & columns) and bool({"法人代表", "工商注册id", "注册资金"} & columns)


def _is_investment_event_table(columns: set[str]) -> bool:
    return "融资方" in columns and "投资方" in columns


def _is_institution_table(columns: set[str]) -> bool:
    return "机构名称" in columns and "投资方" not in columns


def _is_news_table(columns: set[str]) -> bool:
    return bool({"content", "新闻内容", "内容"} & columns) and bool({"title", "新闻标题", "标题"} & columns)


def _split_investors(value: str) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []

    # English firm names (e.g. "GGV Capital") legitimately contain spaces, so a
    # blind space-split shatters them into fake investors. Split only on explicit
    # separators; fall back to space-split only when every token is purely CJK.
    separator_parts = [p.strip() for p in re.split(r"[\u3001\uff0c,\uff1b;/\uff5c|\n\r\t]+", raw) if p.strip()]
    if len(separator_parts) != 1:
        return separator_parts if separator_parts else [raw]

    space_parts = [p.strip() for p in separator_parts[0].split(" ") if p.strip()]
    if len(space_parts) > 1 and all(re.search(r"[\u4e00-\u9fff]", p) for p in space_parts):
        return space_parts
    return separator_parts
