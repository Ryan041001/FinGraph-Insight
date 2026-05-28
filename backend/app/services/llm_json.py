from __future__ import annotations

import json
import re
from typing import Any


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)```", flags=re.IGNORECASE | re.DOTALL)


def parse_llm_json_object(content: str) -> dict[str, Any]:
    text = str(content or "").strip()
    candidates = [text]
    candidates.extend(match.group(1).strip() for match in _FENCED_JSON_RE.finditer(text))
    extracted = _extract_first_json_value(text)
    if extracted:
        candidates.append(extracted)

    errors: list[str] = []
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            errors.append(str(exc))
            continue
        if isinstance(payload, dict):
            return payload
        errors.append(f"expected JSON object, got {type(payload).__name__}")

    preview = text.replace("\n", " ")[:160]
    raise ValueError(f"LLM output is not a valid JSON object: {preview}; errors={errors[:2]}")


def require_llm_json_list(payload: dict[str, Any], field: str) -> list[Any]:
    value = payload.get(field)
    if not isinstance(value, list):
        raise ValueError(f"LLM output field '{field}' must be a list.")
    return value


def require_llm_json_string(payload: dict[str, Any], field: str, *, allow_blank: bool = False) -> str:
    value = payload.get(field)
    if not isinstance(value, str):
        raise ValueError(f"LLM output field '{field}' must be a string.")
    normalized = value.strip()
    if not allow_blank and not normalized:
        raise ValueError(f"LLM output field '{field}' must be a non-empty string.")
    return normalized


def _extract_first_json_value(text: str) -> str | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            _, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        return text[index:index + end]
    return None
