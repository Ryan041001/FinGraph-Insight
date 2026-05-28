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
- In-memory graph runtime for local development and automated tests when Neo4j is not running.
- Neo4j write-through and read queries when `GRAPH_BACKEND=neo4j`; `/health` performs real Neo4j connectivity checks in that mode.
- `POST /extract` requires a configured LLM. `options.mock=true` is rejected by the API.
- Text2Cypher validates read-only Cypher and executes it against Neo4j when `GRAPH_BACKEND=neo4j`; without LLM/Neo4j it fails explicitly.
- SSE streaming routes for GraphRAG, Hybrid RAG, and stock analysis text output.
- Live HTTP integration coverage in `tests/test_live_http_e2e.py`, which starts a real uvicorn process and exercises the stable backend flow.
- Job run history for manual AKShare update triggers.

Neo4j and external LLM providers are configured through `.env`; local tests can use memory/fake gateways, but runtime APIs no longer fabricate graph, news, or market data.
