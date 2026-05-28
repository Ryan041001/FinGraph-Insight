from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.models.api import GraphEdge, GraphNode, GraphPayload
from app.services.graph_store import stable_id, node_id


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

    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}

    for _, row in frame.fillna("").iterrows():
        company_name = _field(row, "企业名称", "公司名称", "company", "company_name", "name")
        investor_name = _field(row, "投资方", "投资机构", "investor", "institution")
        round_name = _field(row, "轮次", "融资轮次", "round") or "融资"
        amount = _field(row, "金额", "融资金额", "amount")
        event_date = _field(row, "日期", "时间", "date")

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
            properties={"round": round_name, "amount": amount, "date": event_date},
        )

        received_id = f"rel_{stable_id(company_id, 'RECEIVED_FUNDING', event_id, table_path.name)}"
        edges[received_id] = GraphEdge(
            id=received_id,
            source=company_id,
            target=event_id,
            type="RECEIVED_FUNDING",
            label="获得融资",
            properties={"round": round_name, "amount": amount, "date": event_date},
            provenance={"source": table_path.name, "source_text": _row_text(row)},
        )

        if investor_name:
            investor_id = node_id("Institution", investor_name)
            nodes[investor_id] = GraphNode(
                id=investor_id,
                label=investor_name,
                type="Institution",
                properties={"name": investor_name},
            )
            invested_id = f"rel_{stable_id(investor_id, 'INVESTED_IN', event_id, table_path.name)}"
            edges[invested_id] = GraphEdge(
                id=invested_id,
                source=investor_id,
                target=event_id,
                type="INVESTED_IN",
                label="投资",
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
