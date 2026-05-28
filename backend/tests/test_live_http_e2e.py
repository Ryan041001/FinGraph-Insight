from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
SERVER_HOST = "127.0.0.1"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((SERVER_HOST, 0))
        return int(sock.getsockname()[1])


def _wait_for_server(base_url: str, timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/health", timeout=2.0)
            if response.status_code == 200:
                return
        except Exception as exc:  # pragma: no cover - only used when server is not ready yet
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"uvicorn server did not become ready: {last_error}")


@pytest.fixture(scope="module")
def live_server():
    port = _find_free_port()
    base_url = f"http://{SERVER_HOST}:{port}"
    env = os.environ.copy()
    env["GRAPH_BACKEND"] = "memory"
    env["MARKET_LIVE_ENABLED"] = "false"
    env["SCHEDULER_ENABLED"] = "true"
    env["OPENAI_API_KEY"] = ""
    env["OPENAI_BASE_URL"] = ""
    env["LLM_MODEL"] = ""
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", SERVER_HOST, "--port", str(port)],
        cwd=BACKEND_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_server(base_url)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_live_http_backend_flow_without_external_dependencies(live_server):
    base_url = live_server
    client = httpx.Client(base_url=base_url, timeout=30.0)

    extract_payload = {
        "text": "端测云链科技有限公司完成Pre-A轮融资，端测高榕资本跟投。",
        "options": {"mock": True, "self_refine": False, "judge": False},
    }
    document_payload = {
        "doc_id": "live_e2e_doc_001",
        "title": "端测云链融资新闻",
        "text": "端测云链科技有限公司完成Pre-A轮融资，端测高榕资本跟投，融资金额1200万元。",
        "metadata": {"source": "live_http_e2e", "pub_date": "2026-05-28"},
    }

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["neo4j"] == "memory"

    first_import = client.post("/datasets/import", json={"dataset": "sample_graph"})
    second_import = client.post("/datasets/import", json={"dataset": "sample_graph"})
    assert first_import.status_code == 200
    assert second_import.status_code == 200
    assert first_import.json()["status"] == "success"
    assert second_import.json()["nodes_created"] == 0
    assert second_import.json()["relationships_created"] == 0

    extract_response = client.post("/extract", json=extract_payload)
    assert extract_response.status_code == 200
    extracted = extract_response.json()
    assert extracted["entities"]
    assert extracted["relationships"]

    first_graph_import = client.post("/graph/import", json=extracted)
    second_graph_import = client.post("/graph/import", json=extracted)
    assert first_graph_import.status_code == 200
    assert second_graph_import.status_code == 200
    assert first_graph_import.json()["relationships_created"] >= 1
    assert second_graph_import.json()["relationships_created"] == 0

    profile = client.get("/graph/company/端测云链科技有限公司", params={"depth": 2})
    assert profile.status_code == 200
    profile_payload = profile.json()
    assert profile_payload["company"]["name"] == "端测云链科技有限公司"
    assert profile_payload["graph"]["nodes"]
    assert any("端测云链科技有限公司" in edge["provenance"]["source_text"] for edge in profile_payload["graph"]["edges"])

    subgraph = client.get("/graph/subgraph", params={"entity": "端测云链科技有限公司", "depth": 2, "limit": 20})
    assert subgraph.status_code == 200
    assert len(subgraph.json()["nodes"]) >= 3
    assert len(subgraph.json()["edges"]) >= 2

    path = client.get(
        "/graph/path",
        params={"source": "端测高榕资本", "target": "端测云链科技有限公司", "max_depth": 3},
    )
    assert path.status_code == 200
    path_payload = path.json()
    assert path_payload["paths"]
    assert path_payload["paths"][0]["length"] >= 1

    rag_document = client.post("/rag/documents", json=document_payload)
    assert rag_document.status_code == 200
    assert rag_document.json()["chunks_indexed"] >= 1

    text2cypher_safe = client.post("/qa/text2cypher", json={"question": "查询所有公司"})
    assert text2cypher_safe.status_code == 200
    assert text2cypher_safe.json()["safety"]["passed"] is True
    assert "llm_fallback" in text2cypher_safe.json()["safety"]["rules"]

    text2cypher_unsafe = client.post("/qa/text2cypher", json={"question": "删除所有节点"})
    assert text2cypher_unsafe.status_code == 400
    assert text2cypher_unsafe.json()["error"] == "unsafe_cypher"

    jobs_before = client.get("/jobs")
    assert jobs_before.status_code == 200

    run_job = client.post("/jobs/akshare/run")
    assert run_job.status_code == 200
    job_payload = run_job.json()
    assert job_payload["status"] == "success"
    assert job_payload["new_documents"] >= 1

    jobs_after = client.get("/jobs")
    assert jobs_after.status_code == 200
    job_ids = [job["job_run_id"] for job in jobs_after.json()["jobs"]]
    assert job_payload["job_run_id"] in job_ids

    job_detail = client.get(f"/jobs/{job_payload['job_run_id']}")
    assert job_detail.status_code == 200
    assert job_detail.json()["job_run_id"] == job_payload["job_run_id"]

    metrics = client.get("/metrics/extraction")
    assert metrics.status_code == 200
    assert metrics.json()["sample_count"] >= 50

    stock_analysis = client.post(
        "/analysis/stock",
        json={"stock_code": "600000", "company_name": "端测云链科技有限公司"},
    )
    assert stock_analysis.status_code == 200
    assert stock_analysis.json()["target"]["stock_code"] == "600000"
    assert stock_analysis.json()["analysis"]["disclaimer"]

    latest_analysis = client.get("/analysis/stock/600000/latest")
    assert latest_analysis.status_code == 200
    assert latest_analysis.json()["target"]["stock_code"] == "600000"

    kline = client.get(
        "/market/kline/600000",
        params={"market": "A", "period": "daily", "start_date": "2026-05-01", "end_date": "2026-05-28"},
    )
    assert kline.status_code == 200
    kline_payload = kline.json()
    assert kline_payload["data_source"] == "mock"
    assert kline_payload["kline_data"]
    assert "events" in kline_payload

    client.close()
