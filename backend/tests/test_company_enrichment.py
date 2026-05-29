from app.services.company_enrichment_service import (
    _yahoo_symbol,
    enrich_company_by_stock_code,
    reset_enrichment_cache,
)
from app.services.graph_store import graph_store
from app.models.api import GraphNode, GraphPayload

def setup_function():
    reset_enrichment_cache()
    graph_store.clear()


def teardown_function():
    reset_enrichment_cache()
    graph_store.clear()


def test_yahoo_symbol_resolves_a_share_codes():
    assert _yahoo_symbol("600519", "A") == "600519.SS"
    assert _yahoo_symbol("000001", "A") == "000001.SZ"
    assert _yahoo_symbol("300750", "A") == "300750.SZ"
    assert _yahoo_symbol("00700", "HK") == "00700.HK"
    assert _yahoo_symbol("700", "HK") == "0700.HK"


def test_enrich_skips_when_stock_code_empty():
    assert enrich_company_by_stock_code("") is None
    assert enrich_company_by_stock_code("   ") is None


def test_enrich_uses_cached_payload_within_ttl(monkeypatch):
    calls = {"count": 0}

    def fake_fetch(stock_code, market):
        calls["count"] += 1
        return {
            "symbol": "600519.SS",
            "long_name": "Kweichow Moutai",
            "short_name": "MOUTAI",
            "industry": "Beverages - Wineries & Distilleries",
            "sector": "Consumer Defensive",
            "website": "https://www.moutaichina.com",
            "country": "China",
            "employees": 34000,
            "business_summary": "Liquor producer.",
            "market_cap": 2_000_000_000_000,
            "currency": "CNY",
            "source": "yfinance",
        }

    monkeypatch.setattr("app.services.company_enrichment_service._fetch_yfinance_info", fake_fetch)

    first = enrich_company_by_stock_code("600519", "贵州茅台")
    second = enrich_company_by_stock_code("600519", "贵州茅台")

    assert first is not None
    assert second is not None
    assert calls["count"] == 1
    assert first["industry"] == "Beverages - Wineries & Distilleries"


def test_enrich_backfills_graph_company_properties(monkeypatch):
    graph_store.import_graph(
        GraphPayload(
            nodes=[
                GraphNode(id="company_moutai", label="贵州茅台", type="Company", properties={"name": "贵州茅台"}),
            ],
            edges=[],
        )
    )

    monkeypatch.setattr(
        "app.services.company_enrichment_service._fetch_yfinance_info",
        lambda code, market: {
            "symbol": "600519.SS",
            "long_name": "Kweichow Moutai",
            "industry": "Beverages",
            "sector": "Consumer Defensive",
            "website": "https://www.moutaichina.com",
            "country": "China",
            "business_summary": "Liquor.",
            "source": "yfinance",
        },
    )

    enrich_company_by_stock_code("600519", "贵州茅台")

    refreshed = graph_store._find_company("贵州茅台")
    assert refreshed is not None
    assert refreshed.properties.get("industry") == "Beverages"
    assert refreshed.properties.get("sector") == "Consumer Defensive"
    assert refreshed.properties.get("website") == "https://www.moutaichina.com"
    assert refreshed.properties.get("business_summary") == "Liquor."


def test_enrich_returns_none_when_yfinance_payload_is_empty(monkeypatch):
    monkeypatch.setattr(
        "app.services.company_enrichment_service._fetch_yfinance_info",
        lambda code, market: None,
    )
    assert enrich_company_by_stock_code("999999") is None


def test_enrich_does_not_overwrite_existing_industry(monkeypatch):
    graph_store.import_graph(
        GraphPayload(
            nodes=[
                GraphNode(
                    id="company_existing",
                    label="已有行业企业",
                    type="Company",
                    properties={"name": "已有行业企业", "industry": "原始行业"},
                ),
            ],
            edges=[],
        )
    )
    monkeypatch.setattr(
        "app.services.company_enrichment_service._fetch_yfinance_info",
        lambda code, market: {
            "symbol": "000999.SZ",
            "industry": "yfinance 行业",
            "source": "yfinance",
        },
    )
    enrich_company_by_stock_code("000999", "已有行业企业")
    refreshed = graph_store._find_company("已有行业企业")
    assert refreshed.properties["industry"] == "原始行业"


def test_backfill_is_safe_under_concurrent_graph_imports():
    # Reproduces the original crash: backfill reads (iterates _nodes) while a
    # background import inserts new nodes. Must not raise
    # "dictionary changed size during iteration".
    import threading

    graph_store.import_graph(
        GraphPayload(
            nodes=[GraphNode(id="company_target", label="并发企业", type="Company", properties={"name": "并发企业"})],
            edges=[],
        )
    )

    stop = threading.Event()
    errors: list[BaseException] = []

    def importer():
        i = 0
        while not stop.is_set():
            i += 1
            try:
                graph_store.import_graph(
                    GraphPayload(
                        nodes=[GraphNode(id=f"company_bulk_{i}", label=f"批量{i}", type="Company", properties={"name": f"批量{i}"})],
                        edges=[],
                    )
                )
            except BaseException as exc:  # noqa: BLE001 - capture for assertion
                errors.append(exc)
                return

    def backfiller():
        for _ in range(200):
            try:
                graph_store.backfill_company_properties("并发企业", {"industry": "金融科技", "sector": "Financial"})
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)
                return

    writer = threading.Thread(target=importer)
    writer.start()
    try:
        backfiller()
    finally:
        stop.set()
        writer.join(timeout=5)

    assert not errors, f"concurrent access raised: {errors[:1]}"
    refreshed = graph_store._find_company("并发企业")
    assert refreshed is not None
    assert refreshed.properties.get("industry") == "金融科技"
