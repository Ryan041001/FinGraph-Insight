from __future__ import annotations

from typing import Any

from app.models.api import GraphEdge, GraphNode, GraphPayload
from app.services.extraction_service import extract_with_llm
from app.services.graph_runtime import import_extraction_payload_runtime, import_graph_runtime
from app.services.graph_store import ImportStats, node_id, stable_id
from app.services.llm_service import LLMGateway


MAX_NEWS_EVENTS_TO_IMPORT = 5


def news_events_to_graph(company_name: str, events: list[dict[str, Any]]) -> GraphPayload:
    normalized_company = company_name.strip()
    if not normalized_company:
        return GraphPayload(nodes=[], edges=[])

    company_id = node_id("Company", normalized_company)
    nodes: dict[str, GraphNode] = {
        company_id: GraphNode(
            id=company_id,
            label=normalized_company,
            type="Company",
            properties={"name": normalized_company, "source": "merged_runtime_graph"},
        )
    }
    edges: dict[str, GraphEdge] = {}

    for index, event in enumerate(events[:MAX_NEWS_EVENTS_TO_IMPORT], start=1):
        title = _clean_text(event.get("title")) or f"{normalized_company}公开线索{index}"
        evidence = _clean_text(event.get("evidence")) or title
        date = _clean_text(event.get("date")) or "未知"
        source_url = _clean_text(event.get("source_url"))
        event_type = _clean_text(event.get("event_type")) or "public_info"
        sentiment = _clean_text(event.get("sentiment")) or "unknown"
        topic = _clean_text(event.get("topic")) or _topic_label(event_type)

        event_id = f"news_event_{stable_id(normalized_company, title, date, source_url, evidence)}"
        document_id = f"news_doc_{stable_id(source_url or title, evidence)}"
        topic_id = node_id("Topic", topic)

        nodes[event_id] = GraphNode(
            id=event_id,
            label=title,
            type="Event",
            properties={
                "name": title,
                "event_type": event_type,
                "sentiment": sentiment,
                "date": date,
                "description": evidence,
                "source_url": source_url,
                "source": "realtime_news",
            },
        )
        nodes[document_id] = GraphNode(
            id=document_id,
            label=title,
            type="Document",
            properties={
                "title": title,
                "url": source_url,
                "pub_date": date,
                "content": evidence,
                "source": "realtime_news",
            },
        )
        nodes[topic_id] = GraphNode(
            id=topic_id,
            label=topic,
            type="Topic",
            properties={"name": topic, "source": "realtime_news"},
        )

        _add_edge(
            edges,
            source=company_id,
            target=event_id,
            relation_type="MENTIONED_IN",
            label="相关新闻",
            evidence=evidence,
            properties={"date": date, "event_type": event_type, "sentiment": sentiment},
            provenance={"source": "realtime_news", "source_url": source_url, "source_text": evidence},
        )
        _add_edge(
            edges,
            source=event_id,
            target=topic_id,
            relation_type="HAS_TOPIC",
            label="主题",
            evidence=evidence,
            properties={"topic": topic},
            provenance={"source": "realtime_news", "source_url": source_url, "source_text": evidence},
        )
        _add_edge(
            edges,
            source=event_id,
            target=document_id,
            relation_type="SUPPORTED_BY",
            label="证据来源",
            evidence=evidence,
            properties={"date": date},
            provenance={"source": "realtime_news", "source_url": source_url, "source_text": evidence},
        )

    return GraphPayload(nodes=list(nodes.values()), edges=list(edges.values()))


def import_news_events_to_graph(
    company_name: str,
    events: list[dict[str, Any]],
    *,
    gateway: LLMGateway | None = None,
) -> ImportStats:
    base_graph = news_events_to_graph(company_name, events)
    stats = _coerce_stats(import_graph_runtime(base_graph))

    if gateway is None or not events:
        return stats

    for event in events[:MAX_NEWS_EVENTS_TO_IMPORT]:
        text = _news_event_extraction_text(company_name, event)
        if not text:
            continue
        try:
            extraction_payload = extract_with_llm(text, gateway)
            extracted_stats = _coerce_stats(import_extraction_payload_runtime(extraction_payload))
            stats = _merge_stats(stats, extracted_stats)
        except Exception:
            continue

    return stats


def _news_event_extraction_text(company_name: str, event: dict[str, Any]) -> str:
    title = _clean_text(event.get("title"))
    evidence = _clean_text(event.get("evidence"))
    date = _clean_text(event.get("date"))
    return "\n".join(part for part in (f"当前企业：{company_name.strip()}", title, evidence, f"日期：{date}" if date else "") if part)


def _add_edge(
    edges: dict[str, GraphEdge],
    *,
    source: str,
    target: str,
    relation_type: str,
    label: str,
    evidence: str,
    properties: dict[str, Any],
    provenance: dict[str, Any],
) -> None:
    edge_id = f"rel_{stable_id(source, relation_type, target, evidence)}"
    edges[edge_id] = GraphEdge(
        id=edge_id,
        source=source,
        target=target,
        type=relation_type,
        label=label,
        confidence=0.82,
        status="confirmed",
        properties=properties,
        provenance=provenance,
    )


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _topic_label(event_type: str) -> str:
    labels = {
        "product": "产品业务",
        "financing": "融资",
        "risk": "风险",
        "litigation": "诉讼",
        "penalty": "处罚",
        "announcement": "公告",
        "public_info": "公开信息",
    }
    return labels.get(event_type, event_type or "公开信息")


def _coerce_stats(value: Any) -> ImportStats:
    return ImportStats(
        nodes_created=int(getattr(value, "nodes_created", 0)),
        nodes_matched=int(getattr(value, "nodes_matched", 0)),
        relationships_created=int(getattr(value, "relationships_created", 0)),
        relationships_skipped=int(getattr(value, "relationships_skipped", 0)),
    )


def _merge_stats(left: ImportStats, right: ImportStats) -> ImportStats:
    return ImportStats(
        nodes_created=left.nodes_created + right.nodes_created,
        nodes_matched=left.nodes_matched + right.nodes_matched,
        relationships_created=left.relationships_created + right.relationships_created,
        relationships_skipped=left.relationships_skipped + right.relationships_skipped,
    )
