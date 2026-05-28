from app.services.mock_data import sample_graph


def company_profile(name: str, depth: int = 2) -> dict:
    graph = sample_graph(name)
    return {
        "company": {
            "id": "company_demo",
            "name": name,
            "industry": "金融科技",
            "legal_representative": "张三",
        },
        "profile": {
            "shareholders": [],
            "investors": ["红杉资本"],
            "events": ["B轮融资事件"],
            "hidden_relations": [],
            "risk_flags": [],
            "depth": depth,
        },
        "graph": graph.model_dump(),
    }
