from __future__ import annotations

import json
import re
from typing import Any

from app.models.api import GraphPayload
from app.services.graph_rag_service import answer_with_hybrid_context
from app.services.graph_store import InMemoryGraphStore, graph_store as default_graph_store
from app.services.llm_service import LLMGateway, LLMTask
from app.services.vector_store import InMemoryVectorStore, vector_store as default_vector_store


def answer_with_hybrid_rag(
    question: str,
    *,
    entity: str | None = None,
    graph_store: InMemoryGraphStore = default_graph_store,
    vector_store: InMemoryVectorStore = default_vector_store,
    gateway: LLMGateway | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    target_entity = entity or extract_entity_from_question(question)
    graph = graph_store.subgraph(target_entity, depth=2)
    fallback = answer_with_hybrid_context(question, graph, vector_store=vector_store, top_k=top_k)

    if gateway is None:
        return fallback

    try:
        answer = _answer_with_llm(
            question=question,
            graph=graph,
            document_context=fallback["document_context"],
            gateway=gateway,
        )
    except Exception:
        return fallback

    return {**fallback, "answer": answer}


def extract_entity_from_question(question: object) -> str:
    if not isinstance(question, str):
        return "该企业"

    normalized = question.strip()
    if not normalized:
        return "该企业"

    for separator in ("：", ":"):
        if separator in normalized:
            candidate = normalized.split(separator, 1)[0].strip()
            if candidate:
                return candidate

    possessive_match = re.match(r"(?P<entity>[\u4e00-\u9fa5A-Za-z0-9（）()·]+?)的", normalized)
    if possessive_match:
        return possessive_match.group("entity")

    subject_match = re.match(r"(?P<entity>[\u4e00-\u9fa5A-Za-z0-9（）()·]{2,20})(?:融资|投资|股东|收入|风险|关联)", normalized)
    if subject_match:
        return subject_match.group("entity")

    return "该企业"


def _answer_with_llm(
    *,
    question: str,
    graph: GraphPayload,
    document_context: list[dict[str, Any]],
    gateway: LLMGateway,
) -> str:
    content = gateway.complete(
        task=LLMTask.GRAPH_RAG,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是金融知识图谱问答助手。只能基于 supporting_graph 和 document_context 回答，"
                    "优先使用图谱关系，文档片段作为补充。严格输出 json：{\"answer\":\"...\"}。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question,
                        "supporting_graph": graph.model_dump(),
                        "document_context": document_context,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0,
        max_tokens=1024,
    )
    payload = json.loads(content)
    return str(payload.get("answer", "")).strip()
