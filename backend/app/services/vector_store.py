from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from threading import RLock
from typing import Any

from app.data.text_preprocessor import chunk_text


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    doc_id: str
    title: str
    text: str
    metadata: dict[str, Any]
    embedding: list[float]


class HashingEmbeddingProvider:
    def __init__(self, dimensions: int = 256) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in self._tokens(text):
            digest = hashlib.sha1(token.encode("utf-8")).hexdigest()
            index = int(digest[:8], 16) % self.dimensions
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [round(value / norm, 8) for value in vector]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        normalized = re.sub(r"\s+", "", text or "").lower()
        ascii_tokens = re.findall(r"[a-z0-9_]+", normalized)
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
        cjk_bigrams = ["".join(cjk_chars[index : index + 2]) for index in range(max(0, len(cjk_chars) - 1))]
        cjk_trigrams = ["".join(cjk_chars[index : index + 3]) for index in range(max(0, len(cjk_chars) - 2))]
        return [*ascii_tokens, *cjk_chars, *cjk_bigrams, *cjk_trigrams]


class InMemoryVectorStore:
    def __init__(self, embedding_provider: HashingEmbeddingProvider | None = None) -> None:
        self._embedding_provider = embedding_provider or HashingEmbeddingProvider()
        self._chunks: dict[str, DocumentChunk] = {}
        self._lock = RLock()

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()

    def add_document(
        self,
        *,
        doc_id: str,
        text: str,
        title: str = "",
        metadata: dict[str, Any] | None = None,
        max_chars: int = 512,
        overlap_chars: int = 80,
    ) -> int:
        chunks = chunk_text(text, max_chars=max_chars, overlap_chars=overlap_chars)
        with self._lock:
            for index, chunk in enumerate(chunks, start=1):
                chunk_id = f"{doc_id}_{index:04d}"
                self._chunks[chunk_id] = DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    title=title,
                    text=chunk,
                    metadata=dict(metadata or {}),
                    embedding=self._embedding_provider.embed(chunk),
                )
        return len(chunks)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        query_embedding = self._embedding_provider.embed(query)
        with self._lock:
            scored = [
                self._serialize_result(chunk, self._cosine_similarity(query_embedding, chunk.embedding))
                for chunk in self._chunks.values()
            ]
        scored = [item for item in scored if item["score"] > 0]
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[: max(1, top_k)]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        return round(sum(a * b for a, b in zip(left, right, strict=False)), 6)

    @staticmethod
    def _serialize_result(chunk: DocumentChunk, score: float) -> dict[str, Any]:
        return {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "title": chunk.title,
            "text": chunk.text,
            "metadata": chunk.metadata,
            "score": score,
        }


vector_store = InMemoryVectorStore()
