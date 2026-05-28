from app.services.graph_store import graph_store


def company_profile(name: str, depth: int = 2) -> dict:
    return graph_store.company_profile(name, depth=depth)


def subgraph(entity: str, depth: int = 2, limit: int = 80) -> dict:
    return graph_store.subgraph(entity, depth=depth, limit=limit).model_dump()
