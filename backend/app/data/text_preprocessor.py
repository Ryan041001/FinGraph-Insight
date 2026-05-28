from __future__ import annotations

import re

from bs4 import BeautifulSoup


def clean_text(raw_text: str) -> str:
    soup = BeautifulSoup(raw_text or "", "html.parser")
    text = soup.get_text(" ")
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, max_chars: int = 512, overlap_chars: int = 80) -> list[str]:
    cleaned = clean_text(text)
    if not cleaned:
        return []

    sentences = [sentence for sentence in re.split(r"(?<=[。！？!?])", cleaned) if sentence]
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if current and len(current) + len(sentence) > max_chars:
            chunks.append(current)
            current = _overlap_suffix(current, overlap_chars) + sentence
        else:
            current += sentence

    if current:
        chunks.append(current)

    return chunks


def _overlap_suffix(text: str, overlap_chars: int) -> str:
    if overlap_chars <= 0:
        return ""
    return text[-overlap_chars:]
