from app.config import settings
from app.neo4j.connection import get_neo4j_driver
from app.neo4j.reader import Neo4jGraphReader
from app.services.graph_store import graph_store


def _reader() -> Neo4jGraphReader | None:
    if settings.graph_backend.lower() != "neo4j":
        return None
    return Neo4jGraphReader(get_neo4j_driver())


def company_profile(name: str, depth: int = 2) -> dict:
    reader = _reader()
    if reader is not None:
        return reader.company_profile(name, depth=depth)
    return graph_store.company_profile(name, depth=depth)


def subgraph(entity: str, depth: int = 2, limit: int = 80) -> dict:
    reader = _reader()
    if reader is not None:
        return reader.subgraph(entity, depth=depth, limit=limit).model_dump()
    return graph_store.subgraph(entity, depth=depth, limit=limit).model_dump()


def paths(source: str, target: str, max_depth: int = 4) -> dict:
    reader = _reader()
    if reader is not None:
        return {"paths": reader.paths(source, target, max_depth=max_depth)}
    return {"paths": graph_store.paths(source, target, max_depth=max_depth)}
