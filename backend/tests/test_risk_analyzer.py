from app.models.api import GraphEdge, GraphNode, GraphPayload
from app.services.risk_analyzer import analyze_company_risks
from app.data.financial_dataset_loader import _evidence_confidence


def test_risk_analyzer_flags_single_investor_dependence():
    graph = GraphPayload(
        nodes=[
            GraphNode(id="company_x", label="独投企业", type="Company"),
            GraphNode(id="event_x_a", label="独投企业A轮", type="Event", properties={"date": "2024-01-01"}),
            GraphNode(id="institution_lone", label="孤独资本", type="Institution"),
        ],
        edges=[
            GraphEdge(id="rel_x_evt", source="company_x", target="event_x_a", type="RECEIVED_FUNDING", label="获得融资"),
            GraphEdge(id="rel_lone_evt", source="institution_lone", target="event_x_a", type="INVESTED_IN", label="投资"),
        ],
    )

    flags = analyze_company_risks("独投企业", graph)
    codes = {flag["code"] for flag in flags}
    assert "single_investor_dependence" in codes


def test_risk_analyzer_flags_event_density():
    nodes = [GraphNode(id="company_dense", label="密集企业", type="Company")]
    edges = []
    for i in range(3):
        event_id = f"event_dense_{i}"
        nodes.append(GraphNode(id=event_id, label=f"密集企业事件{i}", type="Event", properties={"date": f"2023-0{i+1}-15"}))
        edges.append(GraphEdge(id=f"rel_dense_{i}", source="company_dense", target=event_id, type="RECEIVED_FUNDING", label="获得融资"))

    flags = analyze_company_risks("密集企业", GraphPayload(nodes=nodes, edges=edges))
    codes = {flag["code"] for flag in flags}
    assert "event_density_high" in codes


def test_risk_analyzer_flags_amount_undisclosed():
    graph = GraphPayload(
        nodes=[
            GraphNode(id="company_undisclosed", label="信披企业", type="Company"),
            GraphNode(id="event_u1", label="事件1", type="Event"),
            GraphNode(id="event_u2", label="事件2", type="Event"),
        ],
        edges=[
            GraphEdge(id="rel_u1", source="company_undisclosed", target="event_u1", type="RECEIVED_FUNDING", label="获得融资", properties={"amount": "未披露"}),
            GraphEdge(id="rel_u2", source="company_undisclosed", target="event_u2", type="RECEIVED_FUNDING", label="获得融资", properties={"amount": ""}),
        ],
    )

    flags = analyze_company_risks("信披企业", graph)
    codes = {flag["code"] for flag in flags}
    assert "amount_undisclosed" in codes


def test_risk_analyzer_returns_empty_when_no_rule_triggers():
    graph = GraphPayload(
        nodes=[
            GraphNode(id="company_clean", label="健康企业", type="Company"),
            GraphNode(id="event_c1", label="事件1", type="Event", properties={"date": "2022-03-01"}),
            GraphNode(id="event_c2", label="事件2", type="Event", properties={"date": "2024-09-01"}),
            GraphNode(id="institution_a", label="机构A", type="Institution"),
            GraphNode(id="institution_b", label="机构B", type="Institution"),
        ],
        edges=[
            GraphEdge(id="rel_c1", source="company_clean", target="event_c1", type="RECEIVED_FUNDING", label="获得融资", properties={"amount": "1亿元"}),
            GraphEdge(id="rel_c2", source="company_clean", target="event_c2", type="RECEIVED_FUNDING", label="获得融资", properties={"amount": "2亿元"}),
            GraphEdge(id="rel_a_c1", source="institution_a", target="event_c1", type="INVESTED_IN", label="投资"),
            GraphEdge(id="rel_b_c2", source="institution_b", target="event_c2", type="INVESTED_IN", label="投资"),
        ],
    )

    flags = analyze_company_risks("健康企业", graph)
    assert flags == []


def test_evidence_confidence_full_information():
    assert _evidence_confidence("1.5亿元", "2024-03-15") == 1.0


def test_evidence_confidence_undisclosed_amount():
    assert _evidence_confidence("金额未披露", "2024-03-15") == 0.75


def test_evidence_confidence_partial_information():
    assert _evidence_confidence("", "2024-03-15") == 0.85
    assert _evidence_confidence("1亿元", "") == 0.85


def test_evidence_confidence_no_information():
    assert _evidence_confidence("", "") == 0.7
    assert _evidence_confidence(None, None) == 0.7
