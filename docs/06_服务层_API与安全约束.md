# 06 后端 API 与安全约束

## 1. API 设计原则

完整接口契约、请求响应示例和页面映射见 [09_工程层_详细架构落地方案.md](09_工程层_详细架构落地方案.md)。本文件重点保留 API 原则和安全约束。

- 前后端接口尽早固定，减少联调成本。
- 所有写入 Neo4j 的接口必须经过 schema 校验。
- LLM 输出不得直接执行或直接入库。
- Text2Cypher 只能执行只读查询。
- 错误响应要返回可读原因，不能只返回异常堆栈。

## 2. 核心接口

### 2.1 健康检查

```text
GET /health
```

返回：

```json
{
  "status": "ok",
  "neo4j": "memory",
  "scheduler": "running"
}
```

说明：

- `neo4j=memory`：当前后端使用内存图运行态，仅适合本地开发和自动化测试。
- `neo4j=ok`：当 `GRAPH_BACKEND=neo4j` 时，后端已真实探活 Neo4j 连接。
- `neo4j=unavailable`：当 `GRAPH_BACKEND=neo4j` 时，Neo4j 不可连接。

### 2.2 实时抽取

```text
POST /extract
```

请求：

```json
{
  "text": "红杉资本领投了某科技公司B轮融资。",
  "options": {
    "self_refine": true,
    "judge": true,
    "mock": false
  }
}
```

返回：

```json
{
  "document": {
    "title": null,
    "content_hash": "..."
  },
  "entities": [],
  "relationships": [],
  "warnings": []
}
```

说明：业务运行时不允许 mock 抽取。`options.mock=true` 会返回 `400 mock_disabled`；未配置 LLM 时返回 `502 llm_error`。

### 2.3 抽取结果入库

```text
POST /graph/import
```

用途：

- 将前端确认后的抽取结果写入图谱运行态。
- 入库前再次做实体消歧、关系 ID 计算和置信度校验。
- 当前所有写入都会进入内存图，保证查询接口即时可用。
- 当 `GRAPH_BACKEND=neo4j` 时，同时写穿 Neo4j，查询接口也优先走 Neo4j reader。

### 2.4 企业画像

```text
GET /graph/company/{name}
```

参数：

- `depth`：默认 2，最大 3。
- `include_pending`：默认 false。

### 2.5 路径查询

```text
GET /graph/path
```

参数：

- `source`
- `target`
- `max_depth`

### 2.6 GraphRAG 问答

```text
POST /qa/graph-rag
```

请求：

```json
{
  "question": "红杉资本投资过哪些教育行业公司？"
}
```

返回：

```json
{
  "answer": "根据图谱信息...",
  "supporting_graph": {
    "nodes": [],
    "edges": []
  },
  "citations": [],
  "retrieval": {}
}
```

流式接口：

```text
POST /qa/graph-rag/stream
POST /qa/hybrid-rag/stream
POST /analysis/stock/stream
```

流式接口使用 SSE，事件包括 `metadata`、`ping`、`delta`、`done`、`error`。

### 2.7 Text2Cypher

```text
POST /qa/text2cypher
```

返回：

```json
{
  "cypher": "MATCH ... RETURN ... LIMIT 50",
  "table": {
    "columns": [],
    "rows": []
  },
  "graph": {
    "nodes": [],
    "edges": []
  },
  "safety": {
    "passed": true,
    "reason": "read-only query"
  }
}
```

说明：后端已实现只读安全校验；当 `GRAPH_BACKEND=neo4j` 时执行真实 Neo4j 只读查询。LLM 或 Neo4j 不可用时返回错误，不返回模板假结果。

### 2.8 定时任务状态

```text
GET /jobs
POST /jobs/akshare/run
GET /jobs/{job_run_id}
```

### 2.9 K 线行情详情（P1）

```text
GET /market/kline/{stock_code}
```

该接口只给上市公司节点详情抽屉使用。K 线数据不写入 Neo4j，只和图谱事件在前端做联动展示。

查询参数：

- `market`：`A` 或 `HK`，P1 先支持 `A`。
- `period`：`daily`、`weekly`、`monthly`，P1 先支持 `daily`。
- `start_date`：可选，默认近 6 个月。
- `end_date`：可选，默认今天。
- `adjust`：默认 `qfq`。

## 3. Text2Cypher 安全限制

Text2Cypher 是高风险功能，必须限制。

### 3.1 只读白名单

允许关键词：

- `MATCH`
- `OPTIONAL MATCH`
- `WHERE`
- `WITH`
- `RETURN`
- `ORDER BY`
- `LIMIT`
- `SKIP`

禁止关键词：

- `CREATE`
- `MERGE`
- `DELETE`
- `DETACH DELETE`
- `SET`
- `REMOVE`
- `DROP`
- `CALL dbms`
- `CALL apoc`

### 3.2 Schema 白名单

LLM 生成的查询还必须使用项目图谱 schema 中的 label 和关系类型。安全但不存在的 schema，例如 `Investor` 或 `INVESTS_IN`，会被拒绝，避免生成“能执行但查不到结果”的查询。
- `LOAD CSV`
- `CREATE INDEX`
- `CREATE CONSTRAINT`

### 3.2 自动限制

- 如果模型没有生成 `LIMIT`，后端自动追加 `LIMIT 50`。
- 如果模型生成的 `LIMIT` 大于 100，后端改为 100。
- 查询超时时间限制为 5 秒。
- 最大路径深度限制为 3。

### 3.3 执行前校验

后端流程：

1. 移除注释。
2. 统一大小写做关键词扫描。
3. 检查是否包含禁止关键词。
4. 检查是否是只读语句。
5. 检查是否设置 `LIMIT`。
6. 检查路径深度。
7. 校验通过后才允许进入执行层。

当前实现已完成 1 到 7；只读查询仅在安全校验通过后执行。

### 3.4 失败返回

如果安全校验失败，返回：

```json
{
  "error": "unsafe_cypher",
  "message": "生成的 Cypher 包含写操作关键词 SET，已拒绝执行。",
  "cypher": "MATCH ... SET ..."
}
```

## 4. 配置项

`.env.example` 至少包含：

```text
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_FALLBACK_BASE_URLS=
LLM_MODEL=
LLM_FALLBACK_MODELS=
LLM_TIMEOUT_SECONDS=120
LLM_TEXT2CYPHER_TIMEOUT_SECONDS=45
LLM_NEWS_TIMEOUT_SECONDS=90
LLM_STREAM_TIMEOUT_SECONDS=120
LLM_MAX_RETRIES=1
LLM_RETRY_BACKOFF_SECONDS=0.2
LLM_CIRCUIT_BREAKER_FAILURES=3
LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS=30
GRAPH_BACKEND=memory
MARKET_LIVE_ENABLED=true
MARKET_KLINE_CACHE_TTL_SECONDS=300
MARKET_KLINE_CACHE_DIR=.cache/kline
SCHEDULER_ENABLED=true
AKSHARE_UPDATE_CRON=0 */6 * * *
```

## 5. 错误码

| 错误码 | 含义 |
| --- | --- |
| `invalid_input` | 请求字段不完整或格式错误 |
| `llm_output_invalid` | LLM 输出无法通过 schema 校验 |
| `entity_resolution_failed` | 实体消歧失败 |
| `low_confidence` | 置信度低于入库阈值 |
| `unsafe_cypher` | Cypher 安全校验失败 |
| `neo4j_error` | 图数据库异常 |
| `scheduler_error` | 定时任务异常 |
| `market_data_error` | 行情数据获取异常 |

## 6. 最小测试用例

- `/health` 在 memory 模式返回 `neo4j=memory`，在 Neo4j 模式能检测真实连接。
- `/extract` 对标准新闻返回合法结构。
- `/graph/import` 重复调用不产生重复关系。
- `/qa/text2cypher` 拒绝 `DELETE`、`SET`、`MERGE`。
- `/jobs/akshare/run` 能手动触发更新并返回日志。
- `/market/kline/{stock_code}` 成功时返回 `data_source=yfinance`、`data_source=yahoo_chart` 或 `data_source=akshare`；同参请求在 `MARKET_KLINE_CACHE_TTL_SECONDS` 内返回 `cached=true`；配置 `MARKET_KLINE_CACHE_DIR` 后会在进程重启后继续复用同参缓存；缓存过期后如果外部源全失败，会返回最近一次真实缓存并标记 `cache_status=stale_if_error`；没有可用真实缓存时返回 `market_data_error`，不返回 mock K 线。
