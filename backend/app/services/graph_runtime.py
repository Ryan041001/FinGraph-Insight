from __future__ import annotations

from typing import Any

from app.config import settings
from app.models.api import GraphPayload
from app.neo4j.connection import create_neo4j_driver
from app.neo4j.writer import Neo4jGraphWriter
from app.services.graph_store import graph_store


def import_graph_runtime(
    graph: GraphPayload,
    memory_store: Any = graph_store,
    neo4j_writer: Any | None = None,
) -> Any:
    stats = memory_store.import_graph(graph)
    if settings.graph_backend == "neo4j":
        writer = neo4j_writer or Neo4jGraphWriter(create_neo4j_driver())
        writer.write_graph(graph)
    return stats
