import pandas as pd

from app.data.akshare_fetcher import normalize_news_frame
from app.services.scheduler_service import run_akshare_update


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


def test_run_akshare_update_records_counts_from_fetcher():
    def fake_fetcher():
        return [
            {"title": "新闻1", "content": "正文1", "source": "test", "pub_date": "2024-01-01"},
            {"title": "新闻2", "content": "正文2", "source": "test", "pub_date": "2024-01-02"},
        ]

    job = run_akshare_update(fetcher=fake_fetcher)

    assert job.status == "success"
    assert job.new_documents == 2
    assert job.new_entities == 0
    assert job.new_relationships == 0
    assert job.failed_items == 0
