# Repository Guidelines

## Project Structure & Module Organization

FinGraph Insight is a full-stack financial knowledge graph demo. Backend code lives in `backend/app/`: FastAPI entrypoints in `main.py`, Pydantic contracts in `models/`, Neo4j helpers in `neo4j/`, and domain logic in `services/`.

Frontend code lives in `frontend/src/`: API clients in `api/`, reusable components in `components/`, product logic in `product/`, and route views in `views/`. Documentation is in `docs/`; sample datasets are under `data/`; generated reports belong in `reports/`.

## Build, Test, and Development Commands

- `cd backend && python -m pip install -r requirements.txt`: install backend deps.
- `cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`: run the API.
- `cd backend && pytest`: run backend contract tests.
- `cd frontend && npm install`: install frontend deps.
- `cd frontend && npm run dev`: start the Vite development server.
- `cd frontend && npm run build`: type-check and build the frontend.
- `cd frontend && npm test`: run frontend tests once.
- `docker compose up --build`: run Neo4j, backend, and frontend together.

## Coding Style & Naming Conventions

Use 4-space indentation for Python and 2-space indentation for Vue, TypeScript, JSON, and CSS. Prefer typed Pydantic request/response models for API contracts. Keep Vue components in `PascalCase.vue`; frontend tests sit next to the unit as `*.test.ts`. Use service names such as `market_service.py`.

## Testing Guidelines

Backend tests use `pytest`; frontend tests use `vitest` with Vue Test Utils and jsdom. Add focused tests for API contracts, product adapters, storage behavior, and Vue interactions. There is no fixed coverage threshold yet, but new behavior should include regression coverage.

## Branching, Commits, and Pull Requests

Do not develop directly on `main`. After one feature is complete and before starting the next, return to `main`, pull latest, then create a new feature branch:

```powershell
git switch main
git pull --ff-only
git switch -c feat/<short-topic>
```

Use lowercase, hyphenated branch names, such as `feat/risk-report-export`.

Commit messages must follow `<scope>(<type>): <Chinese summary>`. Examples: `frontend(feat): 新增自选股筛选`, `backend(fix): 校验 Cypher 查询限制`, `docs(chore): 更新启动说明`. Use types such as `feat`, `fix`, `test`, `docs`, `refactor`, and `chore`.

Pull requests should include a summary, test results, linked issue or task context, and screenshots for UI changes.

## Security & Configuration Tips

Do not commit `.env`, secrets, Neo4j dumps, generated datasets, or local reports. Use `.env.example` to document required variables. The default Neo4j password in `docker-compose.yml` is for local development only.
