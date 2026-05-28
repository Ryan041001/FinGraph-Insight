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
SERVER_HOST = "127.0.0.1"


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((SERVER_HOST, 0))
        return int(sock.getsockname()[1])


def _wait_for_server(base_url: str, timeout_seconds: float = 30.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url}/health", timeout=2.0)
            if response.status_code == 200:
                return
        except Exception as exc:
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(f"neo4j uvicorn server did not become ready: {last_error}")


@pytest.fixture(scope="module")
def neo4j_live_server():
    if os.getenv("RUN_NEO4J_E2E") != "1":
        pytest.skip("set RUN_NEO4J_E2E=1 to run the live Neo4j integration test")

    port = _find_free_port()
    base_url = f"http://{SERVER_HOST}:{port}"
    env = os.environ.copy()
    env["GRAPH_BACKEND"] = "neo4j"
    env["MARKET_LIVE_ENABLED"] = "true"
    env["SCHEDULER_ENABLED"] = "false"
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


def test_live_neo4j_backend_flow_uses_real_financial_datasets(neo4j_live_server):
    client = httpx.Client(base_url=neo4j_live_server, timeout=180.0)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["neo4j"] == "ok"

    import_response = client.post("/datasets/import", json={"dataset": "financial_datasets"}, timeout=900.0)
    assert import_response.status_code == 200
    assert import_response.json()["status"] == "success"

    repeat_import = client.post("/datasets/import", json={"dataset": "financial_datasets"}, timeout=900.0)
    assert repeat_import.status_code == 200
    assert repeat_import.json()["nodes_created"] == 0
    assert repeat_import.json()["relationships_created"] == 0
    assert repeat_import.json()["nodes_skipped"] >= 56100
    assert repeat_import.json()["relationships_skipped"] >= 4772

    profile = client.get("/graph/company/邦盛科技", params={"depth": 2})
    assert profile.status_code == 200
    profile_payload = profile.json()
    assert profile_payload["company"]["name"] == "邦盛科技"
    assert len(profile_payload["graph"]["nodes"]) >= 3
    assert len(profile_payload["graph"]["edges"]) >= 2

    path = client.get(
        "/graph/path",
        params={"source": "国投创业", "target": "邦盛科技", "max_depth": 3},
    )
    assert path.status_code == 200
    path_payload = path.json()
    assert path_payload["paths"]
    first_path = path_payload["paths"][0]
    assert first_path["length"] >= 1
    assert {"国投创业", "邦盛科技"}.issubset({node["label"] for node in first_path["nodes"]})

    unsafe = client.post("/qa/text2cypher", json={"question": "删除所有节点"})
    assert unsafe.status_code == 400
    assert unsafe.json()["error"] == "unsafe_cypher"

    safe_without_llm = client.post("/qa/text2cypher", json={"question": "查询所有公司"})
    assert safe_without_llm.status_code == 502
    assert safe_without_llm.json()["detail"]["error"] == "llm_error"

    kline = client.get(
        "/market/kline/600000",
        params={"market": "A", "period": "daily", "start_date": "2024-01-01", "end_date": "2024-01-10"},
        timeout=120.0,
    )
    assert kline.status_code in {200, 503}
    if kline.status_code == 200:
        assert kline.json()["data_source"] in {"akshare", "yahoo_chart"}
    else:
        assert kline.json()["detail"]["error"] == "market_data_error"

    client.close()
