from __future__ import annotations

from typing import Any

from app.models.api import GraphPayload
from app.services.graph_store import graph_store


DISCLAIMER = "本结果仅用于课程项目演示和研究辅助，不构成投资建议。"


def build_stock_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    stock_code = str(payload.get("stock_code") or "")
    company_name = str(payload.get("company_name") or stock_code or "未知上市公司")
    depth = int(payload.get("depth") or 2)
    graph = graph_store.subgraph(company_name, depth=depth)

    return {
        "target": {
            "stock_code": stock_code,
            "company_name": company_name,
        },
        "fundamentals": {
            "stock_code": stock_code,
            "company_name": company_name,
            "industry": _company_industry(graph),
            "data_time": "local-cache",
        },
        "news_events": _events_from_graph(graph),
        "subgraph": graph.model_dump(),
        "analysis": {
            "summary": f"{company_name}当前研判基于图谱关系、事件和证据链生成，需结合外部数据复核。",
            "opportunity_factors": [],
            "risk_factors": [],
            "graph_insights": _graph_insights(graph),
            "confidence": 0.75 if graph.edges else 0.4,
            "missing_data": ["真实财务字段和实时新闻需接入 AKShare/LLM 后补齐"],
            "disclaimer": DISCLAIMER,
        },
    }


def _company_industry(graph: GraphPayload) -> str:
    for node in graph.nodes:
        if node.type == "Company":
            industry = node.properties.get("industry")
            if isinstance(industry, str) and industry:
                return industry
    return "未知"


def _events_from_graph(graph: GraphPayload) -> list[dict[str, Any]]:
    return [
        {
            "event_type": node.properties.get("event_type", "graph_event"),
            "sentiment": "unknown",
            "title": node.label,
            "date": node.properties.get("date"),
            "source_node_id": node.id,
            "evidence": node.properties.get("description", ""),
        }
        for node in graph.nodes
        if node.type == "Event"
    ]


def _graph_insights(graph: GraphPayload) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    for edge in graph.edges:
        insights.append(
            {
                "title": f"发现{edge.label}关系",
                "path": f"{edge.source} -> {edge.target}",
                "evidence_ids": [edge.id],
            }
        )
    return insights
