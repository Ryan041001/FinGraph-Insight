from __future__ import annotations

from app.models.api import GraphPayload


def answer_with_graph_context(question: str, graph: GraphPayload) -> dict:
    company_names = [node.label for node in graph.nodes if node.type == "Company"]
    target_name = company_names[0] if company_names else "该企业"
    citations = [
        {
            "relation_id": edge.id,
            "source": edge.provenance.get("source", "图谱来源"),
            "source_text": edge.provenance.get("source_text", ""),
        }
        for edge in graph.edges
        if edge.provenance.get("source_text")
    ]
    relation_summaries = [
        f"{_node_label(graph, edge.source)}-{edge.label}->{_node_label(graph, edge.target)}"
        for edge in graph.edges
    ]

    return {
        "answer": f"{target_name}的图谱上下文显示：{'；'.join(relation_summaries) or '暂无可用关系'}。回答仅基于当前支持子图。",
        "entities": [node.label for node in graph.nodes],
        "supporting_graph": graph.model_dump(),
        "citations": citations,
        "question": question,
    }


def _node_label(graph: GraphPayload, node_id: str) -> str:
    for node in graph.nodes:
        if node.id == node_id:
            return node.label
    return node_id
