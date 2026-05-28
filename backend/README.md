# FinGraph Insight Backend

FastAPI backend for the financial knowledge graph demo.

## uv workflow

```powershell
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
uv run pytest
```

## Current backend capabilities

- Contract-compatible FastAPI routes for graph, extraction, QA, jobs, metrics, analysis, and market data.
- In-memory graph store for local development and tests when Neo4j is not running.
- Deterministic extraction fallback for course-demo financial financing text.
- Job run history for manual AKShare update triggers.

Neo4j and external LLM providers are configured through `.env`; local tests do not require those services.
