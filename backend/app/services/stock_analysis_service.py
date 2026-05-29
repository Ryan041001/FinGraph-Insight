from __future__ import annotations

import json
from typing import Any

from app.models.api import GraphPayload
from app.services.company_enrichment_service import enrich_company_by_stock_code
from app.services.news_service import search_news_events
from app.services.graph_store import graph_store
from app.services.llm_service import LLMGateway, LLMTask
from app.services.llm_json import parse_llm_json_object


DISCLAIMER = "本结果仅用于课程项目演示和研究辅助，不构成投资建议。"


def build_stock_analysis(payload: dict[str, Any], news_gateway: LLMGateway | None = None) -> dict[str, Any]:
    stock_code = str(payload.get("stock_code") or "")
    company_name = str(payload.get("company_name") or stock_code or "未知上市公司")
    market = str(payload.get("market") or "A")
    depth = int(payload.get("depth") or 2)
    enrich_enabled = bool(payload.get("enrich_fundamentals", True))

    enrichment: dict[str, Any] | None = None
    if enrich_enabled and stock_code:
        try:
            enrichment = enrich_company_by_stock_code(stock_code, company_name, market=market)
        except Exception:
            enrichment = None

    graph = graph_store.subgraph(company_name, depth=depth)

    news_events = _events_from_graph(graph)
    if payload.get("refresh_news") and news_gateway is not None:
        news_events = [*search_news_events(company_name, news_gateway), *news_events]

    fundamentals = {
        "stock_code": stock_code,
        "company_name": company_name,
        "industry": _company_industry(graph, enrichment),
        "data_time": "local-cache",
    }
    if enrichment:
        fundamentals["sector"] = enrichment.get("sector") or ""
        fundamentals["website"] = enrichment.get("website") or ""
        fundamentals["long_name"] = enrichment.get("long_name") or ""
        fundamentals["country"] = enrichment.get("country") or ""
        fundamentals["employees"] = enrichment.get("employees") or 0
        fundamentals["market_cap"] = enrichment.get("market_cap") or 0
        fundamentals["currency"] = enrichment.get("currency") or ""
        fundamentals["business_summary"] = enrichment.get("business_summary") or ""
        fundamentals["data_source"] = enrichment.get("source") or "yfinance"
        fundamentals["data_time"] = "live"

    missing_data: list[str] = []
    if enrich_enabled and not enrichment:
        missing_data.append("基本面字段补充失败（yfinance 不可用或股票代码无法解析）")

    return {
        "target": {
            "stock_code": stock_code,
            "company_name": company_name,
        },
        "fundamentals": fundamentals,
        "news_events": news_events,
        "subgraph": graph.model_dump(),
        "analysis": {
            "summary": f"{company_name}当前研判基于图谱关系、事件和证据链生成，需结合外部数据复核。",
            "opportunity_factors": [],
            "risk_factors": [],
            "graph_insights": _graph_insights(graph),
            "confidence": 0.75 if graph.edges else 0.4,
            "missing_data": missing_data,
            "disclaimer": DISCLAIMER,
        },
    }


def build_stock_analysis_with_llm(payload: dict[str, Any], gateway: LLMGateway) -> dict[str, Any]:
    base = build_stock_analysis(payload)
    return summarize_stock_analysis_with_llm(base, gateway)


def summarize_stock_analysis_with_llm(base: dict[str, Any], gateway: LLMGateway) -> dict[str, Any]:
    content = gateway.complete(
        task=LLMTask.STOCK_ANALYSIS,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是图谱增强金融研判助手。只能基于输入的 target、fundamentals、news_events、subgraph 生成结构化 JSON。"
                    "不得输出买入、卖出、目标价或收益承诺。"
                ),
            },
            {"role": "user", "content": json.dumps(base, ensure_ascii=False)},
        ],
        temperature=0.1,
        max_tokens=2048,
    )
    analysis = _normalize_llm_analysis(base["analysis"], parse_llm_json_object(content))
    return {**base, "analysis": analysis}


def _normalize_llm_analysis(default_analysis: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    analysis = {
        "summary": str(default_analysis.get("summary", "")),
        "opportunity_factors": list(default_analysis.get("opportunity_factors", [])),
        "risk_factors": list(default_analysis.get("risk_factors", [])),
        "graph_insights": list(default_analysis.get("graph_insights", [])),
        "confidence": float(default_analysis.get("confidence", 0.4)),
        "missing_data": list(default_analysis.get("missing_data", [])),
        "disclaimer": DISCLAIMER,
    }

    summary = raw.get("summary")
    if isinstance(summary, str) and summary.strip():
        analysis["summary"] = summary.strip()

    for field in ("opportunity_factors", "risk_factors", "graph_insights", "missing_data"):
        value = raw.get(field)
        if isinstance(value, list):
            analysis[field] = value

    confidence = raw.get("confidence")
    if isinstance(confidence, int | float):
        analysis["confidence"] = max(0.0, min(1.0, float(confidence)))

    return analysis


def _company_industry(graph: GraphPayload, enrichment: dict[str, Any] | None = None) -> str:
    if enrichment:
        industry = enrichment.get("industry")
        if isinstance(industry, str) and industry:
            return industry
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
