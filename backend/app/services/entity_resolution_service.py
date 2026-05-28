from __future__ import annotations

import re
import unicodedata

from app.services.graph_store import node_id


_COMPANY_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "集团股份",
    "集团",
    "公司",
)


def normalize_entity_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name or "")
    normalized = normalized.strip()
    normalized = re.sub(r"[\s·,，。]+", "", normalized)
    normalized = normalized.replace("（", "").replace("）", "")
    normalized = normalized.replace("(", "").replace(")", "")

    for suffix in _COMPANY_SUFFIXES:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break

    return normalized


class EntityResolver:
    def __init__(self, aliases: dict[str, str] | None = None) -> None:
        self._aliases = {
            normalize_entity_name(alias): canonical
            for alias, canonical in (aliases or {}).items()
        }

    def resolve(self, input_name: str, entity_type: str) -> dict[str, object]:
        normalized_name = normalize_entity_name(input_name)
        resolved_name = self._aliases.get(normalized_name, normalized_name)
        match_type = "alias" if resolved_name != normalized_name else "normalized_name"
        confidence = 0.95 if match_type == "alias" else 0.8

        return {
            "input_name": input_name,
            "normalized_name": normalized_name,
            "resolved_id": node_id(entity_type, resolved_name),
            "resolved_name": resolved_name,
            "match_type": match_type,
            "confidence": confidence,
        }
