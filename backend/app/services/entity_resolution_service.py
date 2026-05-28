from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

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


@dataclass(frozen=True)
class ResolutionCandidate:
    name: str
    type: str
    normalized_name: str
    resolved_id: str

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "ResolutionCandidate":
        name = str(payload.get("name", "")).strip()
        entity_type = str(payload.get("type", "Entity")).strip()
        return cls(
            name=name,
            type=entity_type,
            normalized_name=normalize_entity_name(name),
            resolved_id=str(payload.get("resolved_id") or node_id(entity_type, name)),
        )


class EntityResolver:
    def __init__(
        self,
        aliases: dict[str, str] | None = None,
        candidates: list[dict[str, Any] | ResolutionCandidate] | None = None,
    ) -> None:
        self._aliases = {
            normalize_entity_name(alias): canonical
            for alias, canonical in (aliases or {}).items()
        }
        self._candidates: list[ResolutionCandidate] = [
            candidate if isinstance(candidate, ResolutionCandidate) else ResolutionCandidate.from_mapping(candidate)
            for candidate in (candidates or [])
            if (candidate.name if isinstance(candidate, ResolutionCandidate) else candidate.get("name"))
        ]

    def resolve(self, input_name: str, entity_type: str) -> dict[str, object]:
        normalized_name = normalize_entity_name(input_name)
        alias_name = self._aliases.get(normalized_name)
        if alias_name:
            return self._result(
                input_name=input_name,
                normalized_name=normalized_name,
                resolved_name=alias_name,
                entity_type=entity_type,
                match_type="alias",
                confidence=0.95,
            )

        typed_candidates = [
            candidate
            for candidate in self._candidates
            if candidate.type.lower() == entity_type.lower()
        ]

        for candidate in typed_candidates:
            if input_name.strip() == candidate.name:
                return self._result_from_candidate(input_name, normalized_name, candidate, "exact", 1.0)

        for candidate in typed_candidates:
            if normalized_name == candidate.normalized_name:
                return self._result_from_candidate(input_name, normalized_name, candidate, "normalized", 0.92)

        fuzzy_candidates = self._rank_fuzzy_candidates(normalized_name, typed_candidates)
        if fuzzy_candidates and fuzzy_candidates[0]["confidence"] >= 0.7:
            top = fuzzy_candidates[0]
            return {
                "input_name": input_name,
                "normalized_name": normalized_name,
                "resolved_id": top["resolved_id"],
                "resolved_name": top["name"],
                "match_type": "fuzzy",
                "confidence": top["confidence"],
                "candidates": fuzzy_candidates,
            }

        return self._result(
            input_name=input_name,
            normalized_name=normalized_name,
            resolved_name=normalized_name,
            entity_type=entity_type,
            match_type="normalized_name",
            confidence=0.8,
        )

    @staticmethod
    def _result(
        *,
        input_name: str,
        normalized_name: str,
        resolved_name: str,
        entity_type: str,
        match_type: str,
        confidence: float,
    ) -> dict[str, object]:
        return {
            "input_name": input_name,
            "normalized_name": normalized_name,
            "resolved_id": node_id(entity_type, resolved_name),
            "resolved_name": resolved_name,
            "match_type": match_type,
            "confidence": confidence,
            "candidates": [],
        }

    @staticmethod
    def _result_from_candidate(
        input_name: str,
        normalized_name: str,
        candidate: ResolutionCandidate,
        match_type: str,
        confidence: float,
    ) -> dict[str, object]:
        return {
            "input_name": input_name,
            "normalized_name": normalized_name,
            "resolved_id": candidate.resolved_id,
            "resolved_name": candidate.name,
            "match_type": match_type,
            "confidence": confidence,
            "candidates": [
                {
                    "name": candidate.name,
                    "type": candidate.type,
                    "resolved_id": candidate.resolved_id,
                    "confidence": confidence,
                    "match_type": match_type,
                }
            ],
        }

    @staticmethod
    def _rank_fuzzy_candidates(
        normalized_name: str,
        candidates: list[ResolutionCandidate],
        limit: int = 3,
    ) -> list[dict[str, object]]:
        ranked: list[dict[str, object]] = []
        for candidate in candidates:
            score = round(SequenceMatcher(None, normalized_name, candidate.normalized_name).ratio(), 4)
            ranked.append(
                {
                    "name": candidate.name,
                    "type": candidate.type,
                    "resolved_id": candidate.resolved_id,
                    "confidence": score,
                    "match_type": "fuzzy",
                }
            )
        ranked.sort(key=lambda item: float(item["confidence"]), reverse=True)
        return ranked[:limit]
