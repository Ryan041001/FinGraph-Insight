from __future__ import annotations

from typing import Any

from app.config import settings
from app.models.api import GraphPayload
from app.neo4j.connection import get_neo4j_driver
from app.neo4j.writer import Neo4jGraphWriter
from app.services.graph_store import InMemoryGraphStore, graph_store


def import_graph_runtime(
    graph: GraphPayload,
    memory_store: Any = graph_store,
    neo4j_writer: Any | None = None,
) -> Any:
    stats = memory_store.import_graph(graph)
    if settings.graph_backend == "neo4j":
        writer = neo4j_writer or Neo4jGraphWriter(get_neo4j_driver())
        return writer.write_graph(graph)
    return stats


def import_extraction_payload_runtime(
    payload: dict[str, Any],
    memory_store: Any = graph_store,
    neo4j_writer: Any | None = None,
) -> Any:
    graph = extraction_payload_to_graph(payload)
    return import_graph_runtime(graph, memory_store=memory_store, neo4j_writer=neo4j_writer)


def extraction_payload_to_graph(payload: dict[str, Any]) -> GraphPayload:
    conversion_store = InMemoryGraphStore()
    conversion_store.import_extraction_payload(payload)
    return conversion_store.all_graph()
