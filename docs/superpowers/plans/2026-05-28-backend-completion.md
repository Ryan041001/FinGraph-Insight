# Backend Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete backend hybrid RAG, self-refine extraction, and real sourced gold-standard data, then run the backend for user validation.

**Architecture:** Add focused service modules for hybrid RAG and self-refine, wire them into existing FastAPI routes, and keep evaluator compatibility by storing gold samples as the current flat list shape. All live LLM behavior must keep deterministic fallback paths for local demo reliability.

**Tech Stack:** FastAPI, Pydantic v2, pytest, existing in-memory graph/vector stores, existing LLM gateway abstraction.

---

## File Structure

- Create: `backend/app/services/hybrid_rag_service.py`
  - Owns hybrid graph plus vector retrieval and optional LLM answer generation.
- Create: `backend/app/services/self_refine_service.py`
  - Owns extraction critique and iterative refinement.
- Modify: `backend/app/main.py`
  - Adds `/qa/hybrid-rag` and routes `/extract` self-refine through the new service.
- Modify: `backend/tests/test_vector_store_and_hybrid_rag.py`
  - Adds service and route coverage for hybrid RAG.
- Modify: `backend/tests/test_llm_backed_services.py`
  - Adds self-refine service and route coverage.
- Add: `backend/tests/test_gold_standard_real_data.py`
  - Verifies 50 sourced real gold samples.
- Modify: `data/gold/gold_standard.json`
  - Replaces synthetic-only samples with 50 real public-news samples.

---

### Task 1: Self-Refine Service Tests

**Files:**
- Modify: `backend/tests/test_llm_backed_services.py`
- Create: `backend/app/services/self_refine_service.py`

- [ ] **Step 1: Write failing tests**

Add tests that express the required API before implementation:

```python
from app.services.self_refine_service import extract_with_self_refine


def test_extract_with_self_refine_stops_when_critique_has_no_issues():
    gateway = SequenceGateway(
        [
            '{"entities":[{"name":"星河数据","type":"Company","evidence":"星河数据完成融资"}],'
            '"relationships":[],"warnings":[]}',
            '{"issues":[]}',
        ]
    )

    payload = extract_with_self_refine("星河数据完成融资。", gateway, max_iterations=2)

    assert payload["entities"][0]["name"] == "星河数据"
    assert len(gateway.calls) == 2
    assert gateway.calls[1]["task"] == "extraction"


def test_extract_with_self_refine_refines_when_critique_reports_issues():
    gateway = SequenceGateway(
        [
            '{"entities":[{"name":"星河数据","type":"Company","evidence":"星河数据完成融资"}],'
            '"relationships":[],"warnings":[]}',
            '{"issues":[{"type":"missing_relation","description":"遗漏红杉资本领投关系"}]}',
            '{"entities":[{"name":"星河数据","type":"Company","evidence":"星河数据完成融资"},'
            '{"name":"红杉资本","type":"Institution","evidence":"红杉资本领投"}],'
            '"relationships":[{"head":"红杉资本","relation":"INVESTED_IN","tail":"星河数据",'
            '"evidence":"红杉资本领投星河数据融资","confidence":0.91}],"warnings":[]}',
        ]
    )

    payload = extract_with_self_refine("星河数据完成融资，红杉资本领投。", gateway, max_iterations=1)

    assert len(gateway.calls) == 3
    assert payload["relationships"][0]["relation"] == "INVESTED_IN"
    assert payload["relationships"][0]["status"] == "confirmed"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/test_llm_backed_services.py -q
```

Expected: import failure for `app.services.self_refine_service`.

- [ ] **Step 3: Implement self-refine service**

Create `backend/app/services/self_refine_service.py` with:

```python
from __future__ import annotations

import json
from typing import Any

from app.services.extraction_service import extract_with_deepseek, refine_extraction_with_deepseek
from app.services.llm_service import LLMGateway, LLMTask


def extract_with_self_refine(text: str, gateway: LLMGateway, max_iterations: int = 2) -> dict[str, Any]:
    payload = extract_with_deepseek(text, gateway)
    for _ in range(max(0, max_iterations)):
        critique = critique_extraction(text, payload, gateway)
        if not critique.get("issues"):
            break
        payload = refine_from_critique(text, payload, critique, gateway)
    return payload
```

The same file must define `critique_extraction()` and `refine_from_critique()` using `LLMTask.EXTRACTION`, JSON-only prompts, `temperature=0`, and existing `refine_extraction_with_deepseek` for normalized output.

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
uv run pytest tests/test_llm_backed_services.py -q
```

Expected: self-refine tests pass.

---

### Task 2: Extract Route Integration

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_llm_backed_services.py`

- [ ] **Step 1: Update failing route test**

Adjust `test_extract_route_applies_self_refine_when_enabled` so the sequence includes extraction, critique, and refine responses:

```python
gateway = SequenceGateway(
    [
        '{"entities":[{"name":"星河数据","type":"Company","evidence":"星河数据完成融资"}],'
        '"relationships":[],"warnings":["missing_investor"]}',
        '{"issues":[{"type":"missing_relation","description":"遗漏投资方"}]}',
        '{"entities":[{"name":"星河数据","type":"Company","evidence":"星河数据完成融资"},'
        '{"name":"红杉资本","type":"Institution","evidence":"红杉资本领投"}],'
        '"relationships":[{"head":"红杉资本","relation":"INVESTED_IN","tail":"星河数据",'
        '"evidence":"红杉资本领投星河数据融资","confidence":0.91}],"warnings":[]}',
    ]
)
```

Expected route behavior:

```python
assert len(gateway.calls) == 3
assert payload["relationships"][0]["relation"] == "INVESTED_IN"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
uv run pytest tests/test_llm_backed_services.py::test_extract_route_applies_self_refine_when_enabled -q
```

Expected: failure because route still uses single-pass refine.

- [ ] **Step 3: Modify route**

In `backend/app/main.py`, import and use:

```python
from app.services.self_refine_service import extract_with_self_refine
```

Inside `/extract`:

```python
if request.options.self_refine:
    payload = extract_with_self_refine(request.text, gateway)
else:
    payload = extract_with_deepseek(request.text, gateway)
```

Keep judge and fallback behavior unchanged.

- [ ] **Step 4: Run test to verify pass**

Run:

```powershell
uv run pytest tests/test_llm_backed_services.py::test_extract_route_applies_self_refine_when_enabled -q
```

Expected: pass.

---

### Task 3: Hybrid RAG Service And API

**Files:**
- Create: `backend/app/services/hybrid_rag_service.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_vector_store_and_hybrid_rag.py`

- [ ] **Step 1: Write failing tests**

Add:

```python
from app.services.hybrid_rag_service import answer_with_hybrid_rag


def test_hybrid_rag_service_returns_graph_document_and_retrieval_contract():
    store = InMemoryVectorStore()
    store.add_document(
        doc_id="doc_hybrid_001",
        title="星河数据说明",
        text="星河数据通过数据治理订阅服务获得收入。",
        metadata={"source": "hybrid_test"},
    )

    response = answer_with_hybrid_rag(
        "星河数据的收入模式是什么？",
        vector_store=store,
        gateway=None,
    )

    assert response["retrieval"]["mode"] == "hybrid"
    assert response["supporting_graph"]["nodes"]
    assert response["document_context"]
    assert "数据治理订阅服务" in response["answer"]


def test_hybrid_rag_route_returns_indexed_document_context():
    vector_store.clear()
    client.post(
        "/rag/documents",
        json={
            "doc_id": "doc_hybrid_route_001",
            "title": "路径企业说明",
            "text": "路径企业通过供应链风控平台和年度订阅服务获得收入。",
            "metadata": {"source": "hybrid_route_test"},
        },
    )

    response = client.post("/qa/hybrid-rag", json={"question": "路径企业的收入模式是什么？"})

    assert response.status_code == 200
    assert response.json()["retrieval"]["mode"] == "hybrid"
    assert response.json()["document_context"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
uv run pytest tests/test_vector_store_and_hybrid_rag.py -q
```

Expected: import or 404 failure for new hybrid service/route.

- [ ] **Step 3: Implement service**

Create `backend/app/services/hybrid_rag_service.py` with:

```python
from __future__ import annotations

import json
from typing import Any

from app.models.api import GraphPayload
from app.services.graph_rag_service import answer_with_hybrid_context
from app.services.graph_store import InMemoryGraphStore, graph_store as default_graph_store
from app.services.llm_service import LLMGateway, LLMTask
from app.services.vector_store import InMemoryVectorStore, vector_store as default_vector_store


def answer_with_hybrid_rag(
    question: str,
    *,
    entity: str | None = None,
    graph_store: InMemoryGraphStore = default_graph_store,
    vector_store: InMemoryVectorStore = default_vector_store,
    gateway: LLMGateway | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    target = entity or _extract_entity_from_question(question)
    graph = graph_store.subgraph(target, depth=2)
    fallback = answer_with_hybrid_context(question, graph, vector_store=vector_store, top_k=top_k)
    if gateway is None:
        return fallback
    try:
        answer = _answer_with_llm(question, graph, fallback["document_context"], gateway)
    except Exception:
        return fallback
    return {**fallback, "answer": answer}
```

The file must also include `_extract_entity_from_question()` and `_answer_with_llm()` without importing `app.main`.

- [ ] **Step 4: Add API route**

In `backend/app/main.py`:

```python
from app.services.hybrid_rag_service import answer_with_hybrid_rag
```

Add:

```python
@app.post("/qa/hybrid-rag")
def hybrid_rag(payload: dict) -> dict:
    question = str(payload.get("question", ""))
    entity = payload.get("entity")
    gateway = HttpLLMGateway() if settings.llm_enabled else None
    return answer_with_hybrid_rag(question, entity=entity, gateway=gateway)
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```powershell
uv run pytest tests/test_vector_store_and_hybrid_rag.py -q
```

Expected: pass.

---

### Task 4: Real Gold Standard Data

**Files:**
- Modify: `data/gold/gold_standard.json`
- Add: `backend/tests/test_gold_standard_real_data.py`

- [ ] **Step 1: Write failing test**

Create:

```python
import json
from pathlib import Path


def test_gold_standard_contains_50_sourced_real_samples():
    path = Path(__file__).resolve().parents[2] / "data" / "gold" / "gold_standard.json"
    samples = json.loads(path.read_text(encoding="utf-8"))

    assert len(samples) >= 50
    assert all(sample["id"].startswith("gold_real_") for sample in samples[:50])
    assert all(sample.get("source") for sample in samples[:50])
    assert all(str(sample.get("url", "")).startswith("http") for sample in samples[:50])
    assert all(sample.get("entities") for sample in samples[:50])
    assert all(sample.get("relationships") for sample in samples[:50])
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
uv run pytest tests/test_gold_standard_real_data.py -q
```

Expected: failure because current gold samples are synthetic.

- [ ] **Step 3: Collect and write 50 real samples**

Use public source pages found through web search. Write concise paraphrased facts with source metadata into `data/gold/gold_standard.json`. Use the same flat list shape:

```json
{
  "id": "gold_real_001",
  "text": "金麦特完成超4亿元B轮融资，元璟资本领投。",
  "source": "投资界",
  "url": "https://news.pedaily.cn/202405/534056.shtml",
  "date": "2024-05-17",
  "entities": [
    {"name": "金麦特", "type": "Company"},
    {"name": "元璟资本", "type": "Institution"},
    {"name": "B轮融资", "type": "Event"}
  ],
  "relationships": [
    {"head": "元璟资本", "relation": "INVESTED_IN", "tail": "B轮融资", "attributes": {"role": "领投", "amount": "超4亿元"}},
    {"head": "金麦特", "relation": "RECEIVED_FUNDING", "tail": "B轮融资", "attributes": {"amount": "超4亿元"}}
  ]
}
```

- [ ] **Step 4: Run gold and metrics tests**

Run:

```powershell
uv run pytest tests/test_gold_standard_real_data.py tests/test_qa_and_metrics_services.py tests/test_metrics_service.py -q
```

Expected: pass.

---

### Task 5: Full Backend Verification And Runtime

**Files:**
- No source edits unless tests reveal a regression.

- [ ] **Step 1: Run full backend tests**

Run:

```powershell
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 2: Start backend**

Run:

```powershell
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Expected: server starts and exposes docs at `http://localhost:8000/docs`.

- [ ] **Step 3: Smoke test API**

Run:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod -Method Post http://localhost:8000/qa/hybrid-rag -ContentType "application/json" -Body '{"question":"金麦特融资情况是什么？"}'
```

Expected: health returns `status=ok`; hybrid RAG returns graph, document context, and retrieval metadata.

- [ ] **Step 4: Commit completed backend work**

Commit only files changed for this implementation:

```powershell
git add backend/app backend/tests data/gold/gold_standard.json docs/superpowers/plans/2026-05-28-backend-completion.md
git commit -m "backend(feat): 补全后端混合检索与自修正"
```
