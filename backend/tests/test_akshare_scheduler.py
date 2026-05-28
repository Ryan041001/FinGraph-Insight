import pandas as pd

from app.data.akshare_fetcher import normalize_news_frame
from app.models.api import JobRun
from app.services.graph_runtime import import_extraction_payload_runtime
from app.services.graph_store import ImportStats
from app.services.scheduler_service import build_akshare_scheduler, run_akshare_update


def test_normalize_news_frame_maps_common_akshare_columns():
    frame = pd.DataFrame(
        [
            {
                "新闻标题": "示例科技完成融资",
                "新闻内容": "示例科技完成B轮融资。",
                "文章来源": "东方财富",
                "发布时间": "2024-03-15",
            }
        ]
    )

    docs = normalize_news_frame(frame)

    assert docs == [
        {
            "title": "示例科技完成融资",
            "content": "示例科技完成B轮融资。",
            "source": "东方财富",
            "pub_date": "2024-03-15",
        }
    ]


def test_run_akshare_update_records_pipeline_counts_from_fetcher():
    def fake_fetcher():
        return [
            {"title": "星河数据融资", "content": "星河数据完成B轮融资。", "source": "test", "pub_date": "2024-01-01"},
        ]

    def fake_extractor(text):
        return {
            "document": {"content_hash": "doc_akshare_001"},
            "entities": [
                {"temp_id": "e1", "name": "星河数据", "type": "Company", "resolved_id": "company_xinghe"},
                {"temp_id": "e2", "name": "B轮融资", "type": "Event", "resolved_id": "event_b"},
            ],
            "relationships": [
                {
                    "temp_id": "r1",
                    "head_temp_id": "e1",
                    "relation": "RECEIVED_FUNDING",
                    "tail_temp_id": "e2",
                    "confidence": 0.88,
                    "status": "confirmed",
                }
            ],
            "warnings": [],
        }

    job = run_akshare_update(
        fetcher=fake_fetcher,
        extractor=fake_extractor,
        judge=lambda payload: payload,
        importer=lambda payload: ImportStats(
            nodes_created=2,
            nodes_matched=0,
            relationships_created=1,
            relationships_skipped=0,
        ),
    )

    assert job.status == "success"
    assert job.new_documents == 1
    assert job.new_entities == 2
    assert job.new_relationships == 1
    assert job.failed_items == 0


def test_build_akshare_scheduler_registers_pipeline_job():
    scheduler = build_akshare_scheduler(fetcher=lambda: [])
    jobs = scheduler.get_jobs()

    assert len(jobs) == 1
    assert jobs[0].id == "akshare_update"


def test_run_akshare_update_uses_runtime_importer_by_default(monkeypatch):
    captured = {}

    def fake_pipeline(**kwargs):
        captured.update(kwargs)
        return JobRun(
            job_run_id="job_test",
            status="success",
            started_at="2026-05-28T00:00:00",
            finished_at="2026-05-28T00:00:00",
        )

    monkeypatch.setattr("app.services.scheduler_service.run_extraction_pipeline", fake_pipeline)

    run_akshare_update(fetcher=lambda: [])

    assert captured["importer"] is import_extraction_payload_runtime
