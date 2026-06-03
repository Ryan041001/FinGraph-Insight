import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


import pytest

from app.neo4j.connection import reset_neo4j_driver_cache


@pytest.fixture(autouse=True)
def _reset_neo4j_driver_cache():
    reset_neo4j_driver_cache()
    yield
    reset_neo4j_driver_cache()


@pytest.fixture(autouse=True)
def _reset_dataset_cache():
    from app.main import _DATASET_CACHE, _DATASET_CACHE_LOCK

    with _DATASET_CACHE_LOCK:
        _DATASET_CACHE.clear()
    yield
    with _DATASET_CACHE_LOCK:
        _DATASET_CACHE.clear()


@pytest.fixture(autouse=True)
def _block_company_enrichment_network(request, monkeypatch):
    if "test_company_enrichment" in request.node.nodeid:
        yield
        return
    from app.services import company_enrichment_service

    monkeypatch.setattr(
        company_enrichment_service,
        "_fetch_yfinance_info",
        lambda stock_code, market: None,
    )
    company_enrichment_service.reset_enrichment_cache()
    yield
    company_enrichment_service.reset_enrichment_cache()


@pytest.fixture(autouse=True)
def _reset_news_event_cache():
    from app.services.news_service import reset_news_event_cache

    reset_news_event_cache()
    yield
    reset_news_event_cache()
