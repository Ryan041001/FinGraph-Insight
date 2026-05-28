from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from app.models.api import GraphPayload


_UNDISCLOSED_TOKENS = ("未披露", "未公开", "未透露")
_YEAR_PATTERN = re.compile(r"(\d{4})")


def _is_undisclosed_amount(amount: str) -> bool:
    text = (amount or "").strip()
    if not text:
        return True
    return any(token in text for token in _UNDISCLOSED_TOKENS)


def _extract_year(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    match = _YEAR_PATTERN.search(text)
    if not match:
        return None
    return match.group(1)


def analyze_company_risks(name: str, graph: GraphPayload) -> list[dict[str, Any]]:
    """Infer company-level risk flags from the supplied subgraph.

    Returns a list of flag dicts with keys: ``code``, ``label``, ``severity``,
    ``description``, ``evidence``. Empty list when no rule matches.
    """

    normalized_name = (name or "").strip().lower()
    if not normalized_name:
        return []

    company_node = next(
        (
            node
            for node in graph.nodes
            if node.type == "Company" and node.label.strip().lower() == normalized_name
        ),
        None,
    )
    if company_node is None:
        return []

    company_id = company_node.id
    event_nodes_by_id = {node.id: node for node in graph.nodes if node.type == "Event"}

    received_edges = [
        edge
        for edge in graph.edges
        if edge.type == "RECEIVED_FUNDING"
        and edge.source == company_id
        and edge.target in event_nodes_by_id
    ]
    company_event_ids = {edge.target for edge in received_edges}

    invested_edges = [
        edge
        for edge in graph.edges
        if edge.type == "INVESTED_IN" and edge.target in company_event_ids
    ]

    node_label_by_id = {node.id: node.label for node in graph.nodes}

    flags: list[dict[str, Any]] = []

    investor_ids = {edge.source for edge in invested_edges}
    if len(investor_ids) == 1:
        investor_id = next(iter(investor_ids))
        investor_name = node_label_by_id.get(investor_id, "")
        flags.append(
            {
                "code": "single_investor_dependence",
                "label": "单一投资方依赖",
                "severity": "medium",
                "description": "该企业目前仅记录 1 家投资方，存在融资来源单一风险",
                "evidence": investor_name,
            }
        )

    events_by_year: dict[str, list[str]] = defaultdict(list)
    for event_id in company_event_ids:
        event_node = event_nodes_by_id.get(event_id)
        if event_node is None:
            continue
        year = _extract_year(str(event_node.properties.get("date", "")))
        if year is None:
            continue
        events_by_year[year].append(event_node.label)

    for year in sorted(events_by_year):
        event_names = events_by_year[year]
        if len(event_names) >= 3:
            flags.append(
                {
                    "code": "event_density_high",
                    "label": "事件密集",
                    "severity": "low",
                    "description": f"{year} 年内记录 {len(event_names)} 次融资事件，资金需求集中",
                    "evidence": {"year": year, "events": event_names},
                }
            )

    if received_edges:
        undisclosed_count = sum(
            1
            for edge in received_edges
            if _is_undisclosed_amount(str(edge.properties.get("amount", "")))
        )
        total = len(received_edges)
        if total > 0 and undisclosed_count / total >= 0.5:
            flags.append(
                {
                    "code": "amount_undisclosed",
                    "label": "融资金额未披露占比偏高",
                    "severity": "low",
                    "description": (
                        f"{total} 起融资事件中有 {undisclosed_count} 起未披露金额"
                    ),
                    "evidence": f"{undisclosed_count}/{total}",
                }
            )

    return flags
