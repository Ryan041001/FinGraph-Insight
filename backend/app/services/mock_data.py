from app.models.api import GraphEdge, GraphNode, GraphPayload


def sample_graph(company_name: str = "示例科技") -> GraphPayload:
    company = GraphNode(
        id="company_demo",
        label=company_name,
        type="Company",
        properties={"industry": "金融科技", "legal_representative": "张三"},
    )
    investor = GraphNode(
        id="institution_demo",
        label="红杉资本",
        type="Institution",
        properties={"type": "VC"},
    )
    event = GraphNode(
        id="event_demo",
        label="B轮融资事件",
        type="Event",
        properties={"amount": "3000万元", "date": "2024-03-15"},
    )
    edge_1 = GraphEdge(
        id="rel_invested_demo",
        source=investor.id,
        target=event.id,
        type="INVESTED_IN",
        label="投资",
        confidence=0.92,
        properties={"role": "领投", "round": "B轮"},
        provenance={"source_text": f"红杉资本领投了{company_name}B轮融资。"},
    )
    edge_2 = GraphEdge(
        id="rel_received_demo",
        source=company.id,
        target=event.id,
        type="RECEIVED_FUNDING",
        label="获得融资",
        confidence=0.92,
        properties={"round": "B轮"},
        provenance={"source_text": f"{company_name}完成B轮融资。"},
    )
    return GraphPayload(nodes=[company, investor, event], edges=[edge_1, edge_2])
