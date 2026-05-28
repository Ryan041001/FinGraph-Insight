# 智链金析 / FinGraph Insight

这是一个面向金融关系发现与风险研判的知识图谱和大模型应用，也是课程大作业方向二“知识图谱与大模型应用”的项目。

当前后端已切换为真实数据链路：`/datasets/import` 默认导入 `data/raw/FinancialDatasets`，K 线和新闻只使用 AKShare/LLM 等真实外部源，失败时返回明确错误，不再返回 mock 或 sample graph。`GRAPH_BACKEND=neo4j` 时导入、企业画像、子图、路径和 Text2Cypher 只读查询会走 Neo4j；本地 `memory` 模式仅用于没有 Neo4j 时的开发测试。

## 快速启动

后端本地启动：

```powershell
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端本地启动：

```powershell
cd frontend
npm install
npm run dev
```

Docker Compose：

```powershell
docker compose up --build
```

## 当前状态

- 后端全量测试：`cd backend && uv run pytest`。
- 真实 HTTP 集成测试：`cd backend && uv run pytest tests/test_live_http_e2e.py -q`。
- 常规本地测试可使用 `GRAPH_BACKEND=memory`；课程验收建议启动 Neo4j 并设置 `GRAPH_BACKEND=neo4j`。
- `GET /health` 返回 `neo4j=ok` 才表示真实 Neo4j 可用；`neo4j=memory` 只表示内存运行态。
- LLM 相关接口依赖 `.env` 中的 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`LLM_MODEL`；未配置时返回 `llm_error`，不会使用规则 mock 兜底。

## 文档

项目规划见 [项目规划文档.md](项目规划文档.md) 和 `docs/`。
