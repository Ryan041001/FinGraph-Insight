# Backend P0 Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete backend P0 closure for automated KG updates, hybrid RAG, real extraction metrics, stronger entity resolution, and graph runtime write-through.

**Architecture:** Keep the existing FastAPI/API contracts stable while introducing focused services: entity resolution remains standalone, vector retrieval is an in-memory replaceable boundary, pipeline orchestration lives outside routes, and graph runtime owns writes to memory plus optional Neo4j. Tests drive each behavior before implementation.

**Tech Stack:** FastAPI, Pydantic, pytest, APScheduler, standard-library hashing/difflib/math, existing in-memory graph store, optional Neo4j writer.

---

### Task 1: Entity Resolution

**Files:**
- Modify: `backend/app/services/entity_resolution_service.py`
- Modify: `backend/app/services/extraction_service.py`
- Test: `backend/tests/test_entity_resolution_service.py`

- [ ] Write failing tests for exact, normalized, alias, and fuzzy candidate resolution.
- [ ] Run `uv run pytest tests/test_entity_resolution_service.py -v` and confirm resolver APIs fail before implementation.
- [ ] Implement candidate registry, `ResolutionCandidate`, fuzzy scoring, and extraction normalization integration.
- [ ] Run `uv run pytest tests/test_entity_resolution_service.py tests/test_llm_backed_services.py -v`.

### Task 2: Vector Store and Hybrid RAG

**Files:**
- Create: `backend/app/services/vector_store.py`
- Modify: `backend/app/services/graph_rag_service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_vector_store_and_hybrid_rag.py`

- [ ] Write failing tests for document chunk indexing, vector search ranking, and GraphRAG responses containing both graph and document context.
- [ ] Run `uv run pytest tests/test_vector_store_and_hybrid_rag.py -v` and confirm missing module/functions fail.
- [ ] Implement hashing embeddings, in-memory vector store, document indexing, hybrid answer builder, and an ingestion endpoint.
- [ ] Run `uv run pytest tests/test_vector_store_and_hybrid_rag.py tests/test_qa_and_metrics_services.py -v`.

### Task 3: Automated Pipeline and Scheduler

**Files:**
- Create: `backend/app/services/pipeline_service.py`
- Modify: `backend/app/services/scheduler_service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_pipeline_service.py`
- Test: `backend/tests/test_akshare_scheduler.py`

- [ ] Write failing tests proving fetched news is extracted, indexed, judged, filtered, imported, and counted.
- [ ] Run `uv run pytest tests/test_pipeline_service.py tests/test_akshare_scheduler.py -v` and confirm pipeline behavior is absent.
- [ ] Implement pipeline orchestration with injectable fetcher/extractor/judge/importer/vector store.
- [ ] Add APScheduler lifecycle helpers without forcing external network calls in tests.
- [ ] Run `uv run pytest tests/test_pipeline_service.py tests/test_akshare_scheduler.py tests/test_api_contract.py -v`.

### Task 4: Real Gold Standard Metrics

**Files:**
- Modify: `backend/app/services/metrics_service.py`
- Modify: `data/gold/gold_standard.json`
- Test: `backend/tests/test_metrics_service.py`
- Modify: `backend/tests/test_qa_and_metrics_services.py`

- [ ] Write failing tests where imperfect predictions produce non-1.0 precision/recall/F1 and hallucination rate.
- [ ] Run `uv run pytest tests/test_metrics_service.py tests/test_qa_and_metrics_services.py -v`.
- [ ] Implement prediction scoring, normalization, relation matching, effective import rate, and per-sample summaries.
- [ ] Replace corrupted gold samples with 50 readable Chinese examples preserving the schema.
- [ ] Run `uv run pytest tests/test_metrics_service.py tests/test_qa_and_metrics_services.py -v`.

### Task 5: Graph Runtime Write-Through

**Files:**
- Modify: `backend/app/services/graph_runtime.py`
- Modify: `backend/app/services/graph_store.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_graph_runtime.py`
- Modify: `backend/tests/test_api_contract.py`

- [ ] Write failing tests proving extraction payload imports use runtime and Neo4j writer when enabled.
- [ ] Run `uv run pytest tests/test_graph_runtime.py tests/test_api_contract.py -v`.
- [ ] Implement extraction-payload-to-graph conversion and route runtime integration.
- [ ] Run `uv run pytest tests/test_graph_runtime.py tests/test_api_contract.py -v`.

### Task 6: Full Verification

**Files:**
- Inspect all changed backend files and docs.

- [ ] Run `uv run pytest`.
- [ ] Run `git diff --check`.
- [ ] Review changed files for secrets, generated dumps, broken API contracts, and unrelated churn.
