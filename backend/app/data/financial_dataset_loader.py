from __future__ import annotations

import json
from pathlib import Path

from app.models.api import GraphPayload


def load_graph_payload_from_json(path: str | Path) -> GraphPayload:
    graph_path = Path(path)
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    return GraphPayload.model_validate(payload)
