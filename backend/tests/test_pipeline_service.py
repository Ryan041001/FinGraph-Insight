from app.services.graph_store import ImportStats
from app.services.pipeline_service import run_extraction_pipeline
from app.services.vector_store import InMemoryVectorStore


def test_extraction_pipeline_requires_real_extractor():
    job = run_extraction_pipeline(
        fetcher=lambda: [{"title": "星河数据融资", "content": "星河数据完成B轮融资。", "source": "unit_test"}],
        document_vector_store=InMemoryVectorStore(),
    )

    assert job.status == "failed"
    assert job.new_documents == 1
    assert job.new_relationships == 0
    assert job.failed_items == 1


def test_extraction_pipeline_indexes_judges_imports_and_counts_confirmed_items():
    documents = [
        {
            "title": "星河数据融资",
            "content": "星河数据完成B轮融资，红杉资本领投。",
            "source": "unit_test",
            "pub_date": "2026-05-28",
        }
    ]
    imported_payloads = []
    vector_store = InMemoryVectorStore()

    def extractor(text):
        assert "星河数据" in text
        return {
            "document": {"content_hash": "doc_hash_001"},
            "entities": [
                {"temp_id": "e1", "name": "星河数据", "type": "Company", "resolved_id": "company_xinghe"},
                {"temp_id": "e2", "name": "红杉资本", "type": "Institution", "resolved_id": "institution_sequoia"},
                {"temp_id": "e3", "name": "B轮融资", "type": "Event", "resolved_id": "event_b"},
            ],
            "relationships": [
                {
                    "temp_id": "r1",
                    "head_temp_id": "e2",
                    "relation": "INVESTED_IN",
                    "tail_temp_id": "e3",
                    "confidence": 0.62,
                    "status": "pending_review",
                    "evidence": "红杉资本领投",
                }
            ],
            "warnings": [],
        }

    def judge(payload):
        judged = {**payload, "relationships": [dict(payload["relationships"][0])]}
        judged["relationships"][0]["confidence"] = 0.93
        judged["relationships"][0]["status"] = "confirmed"
        return judged

    def importer(payload):
        imported_payloads.append(payload)
        return ImportStats(nodes_created=3, nodes_matched=0, relationships_created=1, relationships_skipped=0)

    job = run_extraction_pipeline(
        fetcher=lambda: documents,
        extractor=extractor,
        judge=judge,
        importer=importer,
        document_vector_store=vector_store,
    )

    assert job.status == "success"
    assert job.new_documents == 1
    assert job.new_entities == 3
    assert job.new_relationships == 1
    assert job.failed_items == 0
    assert imported_payloads[0]["relationships"][0]["status"] == "confirmed"
    assert vector_store.search("星河数据融资", top_k=1)[0]["metadata"]["source"] == "unit_test"


def test_extraction_pipeline_skips_low_confidence_relationships_before_import():
    payload = {
        "document": {"content_hash": "doc_hash_002"},
        "entities": [
            {"temp_id": "e1", "name": "星河数据", "type": "Company", "resolved_id": "company_xinghe"},
            {"temp_id": "e2", "name": "红杉资本", "type": "Institution", "resolved_id": "institution_sequoia"},
        ],
        "relationships": [
            {
                "temp_id": "r1",
                "head_temp_id": "e2",
                "relation": "INVESTED_IN",
                "tail_temp_id": "e1",
                "confidence": 0.51,
                "status": "pending_review",
            }
        ],
        "warnings": [],
    }
    imported_payloads = []

    job = run_extraction_pipeline(
        fetcher=lambda: [{"title": "低置信度", "content": "缺少明确证据", "source": "unit_test"}],
        extractor=lambda text: payload,
        judge=lambda extracted: extracted,
        importer=lambda filtered: imported_payloads.append(filtered)
        or ImportStats(nodes_created=0, nodes_matched=0, relationships_created=0, relationships_skipped=0),
        document_vector_store=InMemoryVectorStore(),
    )

    assert job.status == "success"
    assert job.new_documents == 1
    assert job.new_relationships == 0
    assert imported_payloads == []
