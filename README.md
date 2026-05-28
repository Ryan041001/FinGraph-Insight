# 智链金析 / FinGraph Insight

这是一个面向金融关系发现与风险研判的知识图谱和大模型应用，也是课程大作业方向二“知识图谱与大模型应用”的项目。

当前后端已经具备内存图运行态下的完整演示闭环：数据导入、文本抽取 mock、抽取结果入库、企业画像、子图、路径、文档索引、GraphRAG/Hybrid RAG 接口、Text2Cypher 安全降级、任务更新、指标评测、股票研判和 K 线 mock 行情。Neo4j 写入路径已接入 `GRAPH_BACKEND=neo4j`，但需要本地或 Docker 中启动 Neo4j 后再做真实落库验证。

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
- 常规本地查询态默认使用 `GRAPH_BACKEND=memory`，`GET /health` 返回 `neo4j=memory`。
- `GRAPH_BACKEND=neo4j` 会启用 Neo4j 写穿和连接探活；`GET /health` 返回 `neo4j=ok` 才表示真实 Neo4j 可用。
- LLM 相关接口依赖 `.env` 中的 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`LLM_MODEL`；演示抽取可用 `options.mock=true` 避免外部模型超时。

## 文档

项目规划见 [项目规划文档.md](项目规划文档.md) 和 `docs/`。
