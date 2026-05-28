from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.models.api import JobRun
from app.services.graph_runtime import import_extraction_payload_runtime
from app.services.graph_store import ImportStats, stable_id
from app.services.vector_store import InMemoryVectorStore, vector_store


DocumentFetcher = Callable[[], list[dict[str, str]]]
Extractor = Callable[[str], dict[str, Any]]
Judge = Callable[[dict[str, Any]], dict[str, Any]]
Importer = Callable[[dict[str, Any]], ImportStats]


def run_extraction_pipeline(
    *,
    fetcher: DocumentFetcher,
    extractor: Extractor | None = None,
    judge: Judge | None = None,
    importer: Importer = import_extraction_payload_runtime,
    document_vector_store: InMemoryVectorStore = vector_store,
    min_import_confidence: float = 0.8,
) -> JobRun:
    started_at = datetime.now().isoformat(timespec="seconds")
    job_run_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    failed_items = 0
    new_entities = 0
    new_relationships = 0

    try:
        documents = fetcher()
    except Exception:
        documents = []
        failed_items += 1

    for document in documents:
        try:
            if extractor is None:
                raise RuntimeError("A real extractor must be provided for the ingestion pipeline.")
            text = _document_text(document)
            doc_id = _document_id(document, text)
            document_vector_store.add_document(
                doc_id=doc_id,
                title=document.get("title", ""),
                text=text,
                metadata={
                    "source": document.get("source", ""),
                    "pub_date": document.get("pub_date", ""),
                    "title": document.get("title", ""),
                },
            )

            extracted = extractor(text)
            judged = judge(extracted) if judge else extracted
            confirmed = _confirmed_payload(judged, min_import_confidence)
            if not confirmed.get("relationships"):
                continue

            stats = importer(confirmed)
            new_entities += stats.nodes_created
            new_relationships += stats.relationships_created
        except Exception:
            failed_items += 1

    return JobRun(
        job_run_id=job_run_id,
        status="success" if failed_items == 0 else "failed",
        started_at=started_at,
        finished_at=datetime.now().isoformat(timespec="seconds"),
        new_documents=len(documents),
        new_entities=new_entities,
        new_relationships=new_relationships,
        failed_items=failed_items,
    )


def _document_text(document: dict[str, str]) -> str:
    title = document.get("title", "").strip()
    content = document.get("content", "").strip()
    return f"{title}\n{content}".strip()


def _document_id(document: dict[str, str], text: str) -> str:
    explicit_id = document.get("id") or document.get("doc_id")
    if explicit_id:
        return explicit_id
    return f"doc_{stable_id(document.get('source', ''), document.get('pub_date', ''), text)}"


def _confirmed_payload(payload: dict[str, Any], min_import_confidence: float) -> dict[str, Any]:
    confirmed_relationships = [
        {
            **relationship,
            "status": "confirmed",
        }
        for relationship in payload.get("relationships", [])
        if float(relationship.get("confidence", 0)) >= min_import_confidence
        and relationship.get("status", "confirmed") != "rejected"
    ]
    return {
        **payload,
        "relationships": confirmed_relationships,
    }
