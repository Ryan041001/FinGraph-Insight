# Backend Completion Design

## Scope

Complete the backend runtime needed for the final project demo. Frontend changes, final report documents, PPT files, and experiment comparison runs are out of scope for this pass.

## Goals

- Add a first-class hybrid RAG service and API endpoint that combines graph context with indexed document chunks.
- Replace single-pass self-refine usage with an explicit extraction critique and refinement loop.
- Add 50 real-news gold-standard samples with source metadata, while preserving compatibility with the existing evaluator.
- Keep the existing fallback behavior so the backend can run without live LLM credentials.
- Start the backend locally after verification so the user can validate the API.

## Current State

- Backend baseline is clean: `uv run pytest` passes with 64 tests.
- `/qa/graph-rag` already appends vector context through `answer_with_hybrid_context`, but no dedicated `/qa/hybrid-rag` endpoint exists.
- `/extract` supports `options.self_refine`, but it calls a single refinement prompt instead of critique-then-refine iterations.
- `data/gold/gold_standard.json` contains 50 synthetic samples. The evaluator expects a flat list, so real samples should use the same shape and may add optional fields such as `source`, `url`, and `date`.
- Experiment comparison scripts are not required in this pass.

## Backend Design

### Hybrid RAG

Create `backend/app/services/hybrid_rag_service.py`.

The service accepts a question, graph store, vector store, and optional LLM gateway. It extracts a target entity using the existing helper logic, retrieves a subgraph, retrieves top document chunks, and returns a stable response contract:

- `answer`
- `question`
- `supporting_graph`
- `document_context`
- `citations`
- `retrieval`

If an LLM gateway is available, it asks the LLM to answer from both graph and document context. If the LLM call fails or is disabled, it uses the deterministic existing `answer_with_hybrid_context` fallback.

Expose `POST /qa/hybrid-rag` in `backend/app/main.py`.

### Self-Refine

Create `backend/app/services/self_refine_service.py`.

The service runs:

1. Initial extraction through `extract_with_deepseek`.
2. Critique prompt checking missing entities, type errors, relation direction errors, unsupported relationships, and weak evidence.
3. Refinement prompt only when critique returns issues.
4. Normalization through existing extraction service helpers.

The API keeps the current `ExtractRequest.options.self_refine` contract. When `self_refine` is true and LLM is enabled, `/extract` uses `extract_with_self_refine`; when false, it uses the existing direct extraction. `judge` remains a separate option after extraction.

### Real Gold Standard

Replace or extend `data/gold/gold_standard.json` with 50 real-news samples. Each sample remains a flat object with:

- `id`
- `text`
- `source`
- `url`
- `date`
- `entities`
- `relationships`

The texts should be concise factual paraphrases based on public source pages, not long copied passages. Relationship types stay inside the current backend vocabulary where possible: `INVESTED_IN`, `RECEIVED_FUNDING`, `COOPERATES_WITH`, `EXECUTIVE_OF`, `LEGAL_REP_OF`, `HOLDS_SHARES`, `SUBSIDIARY_OF`, `BELONGS_TO`.

### Running Backend

After tests pass, start FastAPI with:

```powershell
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

If port 8000 is occupied, use the next available port and report the URL.

## Testing

Add backend tests for:

- Hybrid RAG service and `/qa/hybrid-rag` route.
- Self-refine critique short-circuit and refinement loop.
- `/extract` route using the new self-refine service.
- Gold-standard file shape and minimum 50 real sourced samples.

Run full backend verification with `uv run pytest`.
