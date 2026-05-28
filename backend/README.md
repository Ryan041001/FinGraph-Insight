# FinGraph Insight Backend

FastAPI backend for the financial knowledge graph demo.

## uv workflow

```powershell
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
uv run pytest
```

## Current backend capabilities

- Contract-compatible FastAPI routes for graph, extraction, QA, jobs, metrics, stock analysis, and market data.
- In-memory graph runtime for local development, tests, and stable course demos when Neo4j is not running.
- Optional Neo4j write-through when `GRAPH_BACKEND=neo4j`; `/health` performs real Neo4j connectivity checks in that mode.
- Deterministic extraction fallback via `POST /extract` with `options.mock=true`.
- Text2Cypher read-only safety checks with safe fallback when the LLM is unavailable.
- SSE streaming routes for GraphRAG, Hybrid RAG, and stock analysis text output.
- Live HTTP integration coverage in `tests/test_live_http_e2e.py`, which starts a real uvicorn process and exercises the stable backend flow.
- Job run history for manual AKShare update triggers.

Neo4j and external LLM providers are configured through `.env`; local tests do not require those services. Query endpoints currently read from the in-memory graph runtime, while Neo4j mode is used for connectivity checks and write-through persistence.
