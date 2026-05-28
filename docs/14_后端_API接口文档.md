# 14 后端 API 接口文档

> 本文档对应 2026-05-29 后端调优批次,覆盖运行时稳态加固、用户视角调优与产品功能补齐。所有示例都来自真实 uvicorn live HTTP 探针。

## 0. 通用约定

服务地址:

```text
http://127.0.0.1:8000
```

请求/响应说明:

- 请求和响应均为 JSON,`GET` 用查询参数。
- 所有路径参数会按 UTF-8 解码,前端无需额外 encode 中文。
- 流式 AI 输出接口使用 SSE:`Content-Type: text/event-stream`。
- AI 展示文本允许 Markdown 和受控局部 HTML 片段(必须用 `<!-- html-render-start --> ... <!-- html-render-end -->` 包裹)。
- 流式接口的 `metadata.tool_calls` 提供项目内动作卡片(企业画像、子图、Hybrid 追问、K 线事件)。
- 前端通过 `VITE_API_BASE_URL` 配置后端地址。
- 图结构统一使用 `GraphPayload`:`nodes[]` 和 `edges[]`。

### 0.1 统一错误信封

后端所有 4xx/5xx 响应都遵循同一种 envelope,**前端只需一套错误处理**:

| 来源 | 状态码 | 形状 |
| --- | --- | --- |
| 路由内部抛 `HTTPException` (如 LLM、市场源、Job 不存在) | 4xx/5xx | `{ "detail": { "error": "<code>", "message": "...", ... } }` |
| FastAPI 参数 / Pydantic 校验失败 | 422 | `{ "error": "invalid_input", "message": "请求参数校验失败。", "fields": [{ "field": "...", "message": "...", "type": "..." }] }` |
| Text2Cypher 安全拒绝 | 400 | `{ "error": "unsafe_cypher", "message": "...", "cypher": "" }` |

前端建议封装:

```ts
function pickErrorMessage(payload: any): string {
  return payload?.detail?.message
      ?? payload?.message
      ?? payload?.fields?.[0]?.message
      ?? '请求失败'
}
```

常见错误 code:

| code | 状态码 | 触发场景 |
| --- | --- | --- |
| `invalid_input` | 400 / 422 | 参数缺失、范围越界、类型不符 |
| `mock_disabled` | 400 | `/extract` 请求带 `options.mock=true` |
| `unsafe_cypher` | 400 | Text2Cypher 检测到写操作或 schema 越界 |
| `scheduler_error` | 404 | `/jobs/{id}` 不存在 |
| `llm_error` | 502 | 上游模型超时 / 401 / 5xx;消息中 URL 已脱敏为 `<llm endpoint>` |
| `market_data_error` | 503 | yfinance / Yahoo Chart / AKShare 三源都失败且无 stale 缓存 |
| `metrics_unavailable` | 503 | 未配置真实 predictor |
| `dataset_not_found` | 404 | dataset 文件目录不存在或为空 |

### 0.2 LLM 配置项(从 `.env` 读取)

```text
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_FALLBACK_BASE_URLS=
LLM_MODEL=<model-name>
LLM_FALLBACK_MODELS=
LLM_TIMEOUT_SECONDS=120
LLM_TEXT2CYPHER_TIMEOUT_SECONDS=45
LLM_NEWS_TIMEOUT_SECONDS=90
LLM_STREAM_TIMEOUT_SECONDS=120
LLM_MAX_RETRIES=1
LLM_RETRY_BACKOFF_SECONDS=0.2
LLM_CIRCUIT_BREAKER_FAILURES=3
LLM_CIRCUIT_BREAKER_COOLDOWN_SECONDS=30
```

行情与运行时:

```text
GRAPH_BACKEND=memory                    # memory 或 neo4j
NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD # GRAPH_BACKEND=neo4j 必填
MARKET_KLINE_CACHE_TTL_SECONDS=300
MARKET_KLINE_CACHE_DIR=.cache/kline     # 进程重启可复用磁盘缓存
SCHEDULER_ENABLED=true
AKSHARE_UPDATE_CRON=0 */6 * * *
CORS_ALLOW_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
STOCK_ANALYSIS_CACHE_MAX_SIZE=64
JOB_RUN_HISTORY_MAX_SIZE=50
```

CORS:默认仅放行 `localhost:5173`(本地 Vite 默认端口),可配置 CSV 多源;若设置为 `*` 则 `allow_credentials` 自动关闭。

### 0.3 LLM 错误脱敏

LLM 上游报错时,后端会把消息中的所有 URL 替换为 `<llm endpoint>`,并截断到 240 字符。前端展示原始 `message` 字段是安全的,不会泄露模型代理地址。

### 0.4 AI HTML 输出约束

- 普通回答优先 Markdown。
- 仅流程/对比/卡片场景嵌入局部 HTML。
- 禁止完整页面框架、`<style>`、`class`、`iframe`。
- 样式必须使用内联 `style`。
- 前端先按 `<!-- html-render-start -->` / `<!-- html-render-end -->` 切片,再 allowlist sanitize。

---

## 1. 通用图结构

### 1.1 GraphNode

```json
{
  "id": "company_e2e_cloudchain",
  "label": "端测云链科技有限公司",
  "type": "Company",
  "properties": {
    "name": "端测云链科技有限公司"
  },
  "risk_level": "normal"
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 稳定节点 ID |
| `label` | string | 前端展示名称 |
| `type` | string | `Company`、`Institution`、`Person`、`Event`、`Industry` |
| `properties` | object | 业务属性 |
| `risk_level` | string | 风险等级,默认 `normal` |

### 1.2 GraphEdge

```json
{
  "id": "rel_4ce733c52a825c23",
  "source": "company_e2e_cloudchain",
  "target": "event_e2e_prea",
  "type": "RECEIVED_FUNDING",
  "label": "获得融资",
  "confidence": 0.91,
  "status": "confirmed",
  "properties": {"amount": "1200万元", "round": "Pre-A轮"},
  "provenance": {
    "source_doc_id": "e2e_doc_20260528_002",
    "source_text": "端测云链科技有限公司完成Pre-A轮融资,金额1200万元。",
    "source": "extraction"
  }
}
```

`status` 可能值:`confirmed`、`pending_review`、`rejected`。前端默认只展示 `confirmed`,溯源面板可展开 `pending_review`。

---

## 2. 健康检查

### `GET /health`

用途:检查后端、图存储和调度器状态。

响应:

```json
{
  "status": "ok",
  "neo4j": "ok",
  "scheduler": "disabled"
}
```

- `neo4j` 可能值:`memory`(默认内存)、`ok`(neo4j 探活通过)、`unavailable`(配置了 neo4j 但连不通)。
- `scheduler` 可能值:`running`、`configured`、`disabled`。

---

## 3. 数据集导入

### `POST /datasets/import`

请求:

```json
{ "dataset": "financial_datasets" }
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dataset` | string | 否 | 默认且仅支持 `financial_datasets`,其它值返 400 `invalid_input` |

响应:

```json
{
  "import_run_id": "import_financial_datasets",
  "nodes_created": 56100,
  "relationships_created": 4772,
  "nodes_skipped": 0,
  "relationships_skipped": 0,
  "status": "success"
}
```

**性能特性**:
- 首次:约 14 秒(读 Excel + 入内存图)。
- 二次:**约 80–400 ms**,基于数据目录 mtime 自动复用 GraphPayload 缓存;`nodes_created/relationships_created` 会下降到 0,`nodes_skipped/relationships_skipped` 反映已存在的总量。
- 前端可在用户点击按钮后立即调用一次,得到稳定的图谱基线。

---

## 4. 实时抽取

### `POST /extract`

请求:

```json
{
  "text": "蓝海智能完成A轮融资,启明创投领投。",
  "options": { "self_refine": false, "judge": false, "mock": false }
}
```

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `text` | string | — | 1 到 8000 字符,空字符串或超长返 422 `invalid_input` |
| `options.self_refine` | bool | true | 启用后会触发 2 次 LLM 调用,延迟 +50% 左右 |
| `options.judge` | bool | true | 启用裁判会再触发 1 次 LLM 调用 |
| `options.mock` | bool | false | 传 true 直接 400 `mock_disabled` |

**性能与建议**:

| 配置 | LLM 调用次数 | 实测延迟范围 |
| --- | --- | --- |
| `self_refine=false, judge=false` | 1 | 5 – 12 秒 |
| `self_refine=false, judge=true` | 2 | 10 – 18 秒 |
| `self_refine=true, judge=true` (默认) | 3 | 25 – 35 秒 |

前端首屏演示建议显式传 `{self_refine: false, judge: false}`,确认效果后再开启高质量模式;loading 文案至少给 30 秒预期。

响应:

```json
{
  "document": { "title": null, "content_hash": "xxx" },
  "entities": [
    {
      "temp_id": "e1",
      "name": "蓝海智能",
      "type": "Company",
      "resolved_id": "company_xxx",
      "resolved_name": "蓝海智能",
      "normalized_name": "蓝海智能",
      "resolution_match_type": "normalized_name",
      "resolution_confidence": 0.94,
      "evidence": "蓝海智能完成A轮融资"
    }
  ],
  "relationships": [
    {
      "temp_id": "r1",
      "head_temp_id": "e2",
      "relation": "INVESTED_IN",
      "tail_temp_id": "e3",
      "attributes": { "role": "领投", "round": "A轮" },
      "evidence": "启明创投领投",
      "confidence": 0.9,
      "status": "confirmed"
    }
  ],
  "warnings": []
}
```

LLM 不可用 / 上游异常时返回 `502 llm_error`。

---

## 5. 抽取结果入库

### `POST /graph/import`

入参用 `/extract` 的响应即可。

- 所有导入先落内存图,确保 API 立即可查。
- `GRAPH_BACKEND=neo4j` 时同步写穿到 Neo4j,响应的 `nodes_created/nodes_matched` 来自 `MERGE` 真实计数。
- 重复调用幂等;`relationships_skipped > 0` 表示去重命中,不是失败。

响应:

```json
{
  "nodes_created": 3,
  "nodes_matched": 0,
  "relationships_created": 2,
  "relationships_skipped": 0,
  "status": "success"
}
```

---

## 6. 企业画像

### `GET /graph/company/{name}`

查询参数:

| 参数 | 类型 | 默认 | 范围 | 说明 |
| --- | --- | --- | --- | --- |
| `depth` | int | 2 | 1-3 | 越界返 422 `invalid_input` |
| `include_pending` | bool | false | — | 当前未实际使用 |

**模糊匹配**:精确匹配失败时,自动尝试 substring 匹配。`/graph/company/邦盛` 能命中 `邦盛科技股份有限公司`。

响应:

```json
{
  "company": {
    "id": "company_xxx",
    "name": "端测云链科技有限公司",
    "industry": "未知",
    "legal_representative": "未知"
  },
  "profile": {
    "shareholders": [],
    "investors": ["端测高榕资本"],
    "events": ["端测云链Pre-A轮融资事件"],
    "hidden_relations": [],
    "risk_flags": [],
    "depth": 2
  },
  "graph": { "nodes": [...], "edges": [...] },
  "found": true
}
```

新增字段:

- **`found`**: `true` 表示图谱里存在该实体且有节点/边;`false` 表示未匹配。前端可一次判断,避免依靠 `graph.nodes.length === 0`(歧义)。

`profile.shareholders / hidden_relations / risk_flags` 目前**始终为空数组**(数据集不提供股权比例与风险标记),前端建议默认折叠这些 section 或显示"数据集未提供"。

---

## 7. 企业检索(新增)

### `GET /graph/companies`

用途:为前端"企业搜索框"提供候选列表,解决用户进来不知道能查什么。

查询参数:

| 参数 | 类型 | 默认 | 范围 | 说明 |
| --- | --- | --- | --- | --- |
| `q` | string | "" | — | 模糊关键字,留空返回前 N 条 |
| `limit` | int | 20 | 1-100 | 越界返 422 |

排序规则:**精确匹配 → 前缀匹配 → 包含匹配**,均按图谱原始顺序。

响应:

```json
{
  "query": "邦盛",
  "total": 1,
  "companies": [
    { "id": "company_0baf1af79a1c1f67", "name": "邦盛科技", "industry": "未知" }
  ]
}
```

前端用法建议:

- 搜索框 debounce 300ms 调用一次。
- 拿到 `companies[].name` 后再点跳转 `/graph/company/{name}`。

---

## 8. 子图查询

### `GET /graph/subgraph`

| 参数 | 类型 | 必填 | 默认 | 范围 |
| --- | --- | --- | --- | --- |
| `entity` | string | 是 | — | — |
| `depth` | int | 否 | 2 | 1-3 |
| `limit` | int | 否 | 80 | 1-200 |

`depth` 或 `limit` 越界返 422 `invalid_input`(信封含 `fields[].field=query.depth`)。

响应直接是 `GraphPayload`:

```json
{
  "nodes": [{"id": "company_xxx", "label": "...", "type": "Company"}],
  "edges": [{"id": "rel_xxx", "source": "...", "target": "...", "type": "RECEIVED_FUNDING"}]
}
```

---

## 9. 路径查询

### `GET /graph/path`

| 参数 | 类型 | 必填 | 默认 | 范围 |
| --- | --- | --- | --- | --- |
| `source` | string | 是 | — | — |
| `target` | string | 是 | — | — |
| `max_depth` | int | 否 | 4 | 1-4 |

**返回所有最短长度的路径**(最多 10 条),不再只返一条。同源到目标点之间可能存在多个等长路径,前端可全部画在画布上。

响应:

```json
{
  "paths": [
    {
      "nodes": [
        {"label": "端测高榕资本", "type": "Institution"},
        {"label": "端测云链Pre-A轮融资事件", "type": "Event"},
        {"label": "端测云链科技有限公司", "type": "Company"}
      ],
      "edges": [],
      "length": 2
    }
  ]
}
```

`source == target` 时返回 `length=0` 的自环路径。

---

## 10. GraphRAG 问答

### `POST /qa/graph-rag`

请求:

```json
{ "question": "邦盛科技:这家公司有哪些投资方?" }
```

**问题格式**:

- 推荐格式:`公司名:问题内容` (中英文冒号都行),明确告诉后端目标实体。
- 兼容格式:无冒号时,后端会从问题里**自动搜索图谱中已存在的公司名**作为目标实体,例如 `量子云链科技最近的融资？` 会自动识别 `量子云链科技`。
- 实在识别不到时使用 `该企业` 兜底,supporting_graph 为空,LLM 仍会按"图中无相关信息"回答。

响应:

```json
{
  "answer": "邦盛科技在B/B+/C/战略轮共获得 11 家机构投资...",
  "entities": ["邦盛科技", ...],
  "supporting_graph": { "nodes": [...], "edges": [...] },
  "citations": [...],
  "document_context": [...],
  "retrieval": { "mode": "hybrid", "llm_used": true, "answer_source": "llm" }
}
```

失败返 `502 llm_error`(URL 已脱敏)。

### `POST /qa/graph-rag/stream`

SSE 输出,适合前端逐字展示。

事件:

```text
event: metadata
data: {"supporting_graph":...,"citations":[],"tool_calls":[...],"retrieval":{...}}

event: ping
data: {"status":"waiting"}

event: delta
data: {"text":"##"}

event: delta
data: {"text":" 邦盛"}

event: done
data: {"text":"## 邦盛科技投资方..."}

event: error
data: {"error":"llm_error","message":"模型服务暂不可用"}
```

`metadata.tool_calls`:

```json
[
  {
    "id": "open-subgraph",
    "label": "展开关系子图",
    "description": "查看该实体 2 跳内的节点、关系和证据。",
    "method": "GET",
    "endpoint": "/graph/subgraph",
    "params": {"entity": "邦盛科技", "depth": 2, "limit": 80}
  }
]
```

---

## 11. Hybrid RAG

### `POST /qa/hybrid-rag`

请求:

```json
{ "question": "邦盛科技融资情况", "entity": "邦盛科技" }
```

`entity` 可选;不传时按 GraphRAG 同样规则自动识别。

响应结构与 GraphRAG 类似,额外带 `document_context`(文档向量检索结果)和 `retrieval.document_chunks`。

### `POST /qa/hybrid-rag/stream`

SSE 同上,`metadata` 额外含 `document_context`。

---

## 12. Text2Cypher

### `POST /qa/text2cypher`

请求:

```json
{ "question": "查询邦盛科技的所有投资方" }
```

后端流程:

1. 写意图检查(`删除/创建/修改/更新/清空/写入` 等关键词 → 400 `unsafe_cypher`)。
2. **LLM system prompt 已注入实际图谱 schema**(ALLOWED_LABELS + ALLOWED_RELATIONSHIPS + 运行时新增的 label/relation),减少 LLM 生成幻觉关系被拒。
3. Cypher sanitize:只读、路径深度 ≤ 3、自动加 `LIMIT 50`、schema 白名单。
4. `GRAPH_BACKEND=neo4j` 时执行真实只读 Cypher 并返表;否则只返 Cypher 文本 + `note` 提示。

成功响应(Neo4j 模式):

```json
{
  "cypher": "MATCH (c:Company) RETURN c LIMIT 50",
  "safety": {
    "passed": true,
    "rules": ["read_only", "path_depth_checked", "schema_checked", "limit_added"]
  },
  "table": { "columns": ["c"], "rows": [...] },
  "graph": { "nodes": [...], "edges": [...] }
}
```

**memory 模式响应**(关键差异):

```json
{
  "cypher": "MATCH (c:Company {name:'邦盛科技'})<-[:INVESTED_IN]-(investor) RETURN investor LIMIT 50",
  "safety": { "passed": true, "rules": [...] },
  "table": { "columns": [], "rows": [] },
  "graph": { "nodes": [], "edges": [] },
  "note": "当前未启用 Neo4j 后端,仅返回生成的 Cypher 文本未执行;请将 GRAPH_BACKEND 切换到 neo4j 后查询。"
}
```

前端检测到 `note` 字段时建议在 cypher 展示区域下面加一行灰色文案提示用户。

写操作 / 越界拒绝:

```json
{ "error": "unsafe_cypher", "message": "生成的 Cypher 包含写操作意图,已拒绝执行。", "cypher": "" }
```

状态码:400。

---

## 13. RAG 文档索引

### `POST /rag/documents`

```json
{
  "doc_id": "doc_xxx",
  "title": "标题",
  "text": "正文",
  "metadata": { "source": "akshare", "pub_date": "2026-05-28" }
}
```

响应:

```json
{ "doc_id": "doc_xxx", "chunks_indexed": 1, "status": "success" }
```

---

## 14. 定时任务

### `GET /jobs`

```json
{ "jobs": [...] }
```

按时间倒序;后端保留最近 `JOB_RUN_HISTORY_MAX_SIZE` 条(默认 50)。

### `POST /jobs/akshare/run` ⚠️ 契约已变更(异步)

**变更说明(2026-05-29)**:此接口从同步阻塞改为**立即返回 + 后台执行**。

之前同步跑会卡 30 秒到 2 分钟,前端按钮 loading 体验极差;现在改为后台线程跑 pipeline,接口立即返回 `status=running` 的 JobRun,前端轮询 `/jobs/{id}` 获取最终状态。

立即响应(约 300ms):

```json
{
  "job_run_id": "job_20260529_013433_801797",
  "status": "running",
  "started_at": "2026-05-29T01:34:33",
  "finished_at": null,
  "new_documents": 0,
  "new_entities": 0,
  "new_relationships": 0,
  "failed_items": 0
}
```

前端轮询接口:

```ts
const initial = await runAkshareJob()           // status === "running"
const finalRun = await pollJob(initial.job_run_id, {
  intervalMs: 2000,
  timeoutMs: 180_000,
})
// finalRun.status ∈ {"success", "failed"}
```

完成后的最终响应:

```json
{
  "job_run_id": "job_20260529_013433_801797",
  "status": "success",
  "started_at": "2026-05-29T01:34:33",
  "finished_at": "2026-05-29T01:35:12",
  "new_documents": 10,
  "new_entities": 3,
  "new_relationships": 2,
  "failed_items": 0
}
```

`status` 可能值:`running` → `success` 或 `failed`。

### `GET /jobs/{job_run_id}`

不存在返:

```json
{ "detail": { "error": "scheduler_error", "message": "job run not found" } }
```

状态码:404。

---

## 15. 质量评测

### `GET /metrics/extraction`、`POST /metrics/evaluate`

需要配置真实 predictor;未配置时返 `503 metrics_unavailable`。

真实响应核心:

```json
{
  "sample_count": 50,
  "entity_precision": 0.18,
  "entity_recall": 0.1607,
  "entity_f1": 0.1698,
  "relation_precision": 0.0,
  "relation_recall": 0.0,
  "relation_f1": 0.0,
  "hallucination_rate": 1.0,
  "effective_import_rate": 1.0
}
```

前端展示建议:标题写"金标准评测基线",避免被误读为模型性能。

---

## 16. 股票研判

### `POST /analysis/stock`

请求:

```json
{
  "stock_code": "600000",
  "company_name": "浦发银行",
  "depth": 2,
  "news_window_days": 30,
  "refresh_news": false,
  "use_llm": false
}
```

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `stock_code` | string | 是 | — | — |
| `company_name` | string | 否 | stock_code | 用于关联图谱 |
| `depth` | int | 否 | 2 | 图谱召回深度 |
| `news_window_days` | int | 否 | 30 | — |
| `refresh_news` | bool | 否 | false | 调用 LLM web search 补新闻 |
| `use_llm` | bool | 否 | false | **默认不等待 LLM**;true 时生成结构化研判,失败会保留本地摘要并在 `missing_data` 中追加说明 |

响应:

```json
{
  "target": { "stock_code": "600000", "company_name": "浦发银行" },
  "fundamentals": { ..., "data_time": "local-cache" },
  "news_events": [],
  "subgraph": { "nodes": [...], "edges": [...] },
  "analysis": {
    "summary": "...",
    "opportunity_factors": [],
    "risk_factors": [],
    "graph_insights": [],
    "confidence": 0.75,
    "missing_data": [],
    "disclaimer": "本结果仅用于课程项目演示和研究辅助,不构成投资建议。"
  }
}
```

后端保留每个 `stock_code` 最近一次的研判,LRU 上限 `STOCK_ANALYSIS_CACHE_MAX_SIZE`(默认 64)。

### `GET /analysis/stock/{stock_code}/latest`

优先读缓存;无缓存返回本地图谱摘要,不触发 LLM。

### `POST /analysis/stock/stream`

请求体同 `/analysis/stock`;返回 SSE 文本流。前端展示时务必保留 disclaimer。

---

## 17. K 线行情

### `GET /market/kline/{stock_code}`

| 参数 | 类型 | 默认 | 合法值 |
| --- | --- | --- | --- |
| `market` | string | `A` | `A`、`HK`(其它返 422) |
| `period` | string | `daily` | `daily`、`weekly`、`monthly`(其它返 422) |
| `adjust` | string | `qfq` | `qfq`、`hfq`、`""`(其它返 422) |
| `start_date` | string | 近 180 天 | `YYYY-MM-DD` 或 `YYYYMMDD` |
| `end_date` | string | 当前日期 | 同上 |
| `company_name` | string | — | **可选**,提供后端从图谱拉取该公司 Event 节点拼到 `events[]` |

响应:

```json
{
  "stock_code": "000001",
  "market": "A",
  "display_code": "000001",
  "company_name": "000001",
  "period": "daily",
  "adjust": "qfq",
  "cached": false,
  "data_source": "yfinance",
  "start_date": null,
  "end_date": null,
  "kline_data": [
    {"date": "2025-12-01", "open": 11.6, "close": 11.69, "high": 11.7, "low": 11.53, "volume": 103732271, "amount": 0}
  ],
  "events": [
    {
      "date": "2024-03-15",
      "label": "测试上市公司A轮融资",
      "event_type": "funding",
      "round": "A轮",
      "amount": "1亿元",
      "description": "...",
      "source": "SmoothNLP..."
    }
  ]
}
```

**关键字段**:

- `data_source`:`yfinance`(主)、`yahoo_chart`(备 1)、`akshare`(备 2)。展示文案根据值切换。
- `cached`:true 表示命中 K 线缓存(进程内或磁盘);`cache_status=stale_if_error` 表示三源都失败但返回了过期缓存,UI 应显眼标记。
- `events`:**仅当请求带 `company_name` 时填充**,从图谱中该公司关联的 `Event` 节点拼接,按日期升序;无 `company_name` 时为空数组。
- 历史 bug 修复:之前 yfinance 路径返回的 `date` 全部是 `"0"`,本轮已修。

三源都失败且无 stale 缓存:`503 market_data_error`。

---

## 18. 完整错误格式速查

```json
// 422 参数校验
{
  "error": "invalid_input",
  "message": "请求参数校验失败。",
  "fields": [
    { "field": "query.depth", "message": "Input should be greater than or equal to 1", "type": "greater_than_equal" }
  ]
}

// 400 业务拒绝
{ "error": "unsafe_cypher", "message": "...", "cypher": "" }
{ "detail": { "error": "invalid_input", "message": "unsupported dataset: xxx" } }
{ "detail": { "error": "mock_disabled", "message": "..." } }

// 404
{ "detail": { "error": "scheduler_error", "message": "job run not found" } }
{ "detail": { "error": "dataset_not_found", "message": "..." } }

// 502
{ "detail": { "error": "llm_error", "message": "Client error '401 Unauthorized' for url '<llm endpoint>'..." } }

// 503
{ "detail": { "error": "market_data_error", "message": "..." } }
{ "detail": { "error": "metrics_unavailable", "message": "..." } }
```

---

## 19. 性能与时延参考

| 接口 | 典型时延 | 备注 |
| --- | --- | --- |
| `GET /health` | < 400 ms | Neo4j 模式会做连通性探活 |
| `POST /datasets/import` 首次 | 12 – 18 秒 | 读 Excel + 全量入图 |
| `POST /datasets/import` 二次 | < 500 ms | 基于 mtime 缓存命中 |
| `GET /graph/company/{name}` | < 500 ms | memory 模式 |
| `GET /graph/subgraph` | < 500 ms | memory 模式 |
| `POST /extract` 快配置 | 5 – 12 秒 | `self_refine=false, judge=false` |
| `POST /extract` 默认 | 25 – 35 秒 | `self_refine=true, judge=true` |
| `POST /qa/graph-rag` | 5 – 10 秒 | 单次 LLM |
| `POST /qa/graph-rag/stream` | 首 token 2 – 5 秒 | 总时长视答案长度 |
| `POST /qa/text2cypher` | 4 – 8 秒 | 含 Cypher 校验 |
| `POST /jobs/akshare/run` | < 500 ms 立即返回 | 异步,真实 pipeline 在后台 |
| `GET /market/kline/{code}` 首次 | 1 – 3 秒 | yfinance |
| `GET /market/kline/{code}` 缓存 | < 100 ms | TTL 内 |

前端的所有 loading 提示应基于这张表给用户预期(尤其 extract 默认模式)。
