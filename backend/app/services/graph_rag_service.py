from __future__ import annotations

from app.models.api import GraphPayload
from app.services.format_prompt import HTML_CHAT_FORMAT_INSTRUCTIONS
from app.services.llm_service import LLMGateway, LLMTask
from app.services.vector_store import InMemoryVectorStore, vector_store as default_vector_store
import json


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


def answer_with_hybrid_context(
    question: str,
    graph: GraphPayload,
    *,
    vector_store: InMemoryVectorStore = default_vector_store,
    top_k: int = 5,
) -> dict:
    base = answer_with_graph_context(question, graph)
    document_context = vector_store.search(question, top_k=top_k)
    document_citations = [
        {
            "chunk_id": chunk["chunk_id"],
            "doc_id": chunk["doc_id"],
            "source": chunk["metadata"].get("source", chunk.get("title") or "document"),
            "source_text": chunk["text"],
            "score": chunk["score"],
        }
        for chunk in document_context
    ]

    if document_context:
        document_summary = "；".join(chunk["text"] for chunk in document_context[:2])
        base["answer"] = f"{base['answer']} 文档补充：{document_summary}"

    base["document_context"] = document_context
    base["citations"] = [*base["citations"], *document_citations]
    base["retrieval"] = {
        "mode": "hybrid",
        "graph_nodes": len(graph.nodes),
        "graph_edges": len(graph.edges),
        "document_chunks": len(document_context),
    }
    return base


def answer_with_llm_graph_context(question: str, graph: GraphPayload, gateway: LLMGateway) -> dict:
    content = gateway.complete(
        task=LLMTask.GRAPH_RAG,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是金融知识图谱问答助手。只能基于用户提供的 supporting_graph 回答。"
                    "请输出 json：{\"answer\":\"...\"}，answer 字段可使用 Markdown 和受控局部 HTML。"
                    "不得编造图谱外事实。"
                    f"\n{HTML_CHAT_FORMAT_INSTRUCTIONS}"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"question": question, "supporting_graph": graph.model_dump()},
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0,
        max_tokens=1024,
    )
    payload = json.loads(content)
    base = answer_with_graph_context(question, graph)
    base["answer"] = str(payload.get("answer", base["answer"]))
    return base


def _node_label(graph: GraphPayload, node_id: str) -> str:
    for node in graph.nodes:
        if node.id == node_id:
            return node.label
    return node_id
