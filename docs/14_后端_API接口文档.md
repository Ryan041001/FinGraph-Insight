# 14 后端 API 接口文档

服务地址：

```text
http://127.0.0.1:8000
```

统一约定：

- 请求和响应均为 JSON，除 `GET` 查询参数外。
- 流式 AI 输出接口使用 SSE：`Content-Type: text/event-stream`。
- AI 展示文本允许返回 Markdown 和受控局部 HTML。HTML 片段必须用 `<!-- html-render-start -->` / `<!-- html-render-end -->` 包裹，且只能是局部片段。
- 流式接口的 `metadata.tool_calls` 会提供可渲染为卡片按钮的项目内动作，例如查看企业画像、展开子图、打开 K 线事件。
- 前端默认通过 `VITE_API_BASE_URL` 配置后端地址。
- 图结构统一使用 `GraphPayload`：`nodes` 和 `edges`。
- 本文示例优先采用 2026-05-28 端到端测试的真实返回。
- 本轮 live HTTP 测试已覆盖 `GRAPH_BACKEND=memory` 和 `GRAPH_BACKEND=neo4j` 两种运行态；Neo4j Community 5.26.26 本机联调通过，真实 FinancialDatasets 已落库并可查询。

LLM 配置：

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
MARKET_KLINE_CACHE_TTL_SECONDS=300
MARKET_KLINE_CACHE_DIR=.cache/kline
```

说明：后端默认使用同一个 `LLM_MODEL` 完成抽取、裁判、Text2Cypher、GraphRAG、股票研判和新闻补充；新闻补充任务只是在同一模型调用中额外附带 web search tool。可选配置 `LLM_FALLBACK_MODELS` 与 `OPENAI_FALLBACK_BASE_URLS`，当主模型或主网关出现连接错误、超时、429 或 5xx 时按候选路由降级重试。LLM 请求会附带浏览器风格 `User-Agent` 和 `Accept: application/json`；非流式调用对连接错误、超时、429 和 5xx 做有限重试，流式调用在首包前失败时也会重试；Text2Cypher、新闻和流式任务可单独配置超时；连续失败达到阈值后会短时熔断，避免每次请求都等待上游超时。

LLM JSON 响应会进行对象解析和关键字段类型校验。字段缺失或类型不符合预期时按 `llm_error` 返回，避免空答案、错误列表类型或缺失 Cypher 被误判为成功。

AI HTML 输出约束：

- 普通回答仍优先使用 Markdown。
- 只有流程、对比、风险卡、摘要卡等复杂信息才插入局部 HTML。
- 禁止完整页面框架，禁止 `<style>`、`class`、`iframe` 等。
- 样式必须使用内联 `style`。
- 前端应先按 marker 切分 HTML 片段，再做 allowlist/sanitize 渲染。

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

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 稳定节点 ID |
| `label` | string | 前端展示名称 |
| `type` | string | `Company`、`Institution`、`Person`、`Event`、`Industry` 等 |
| `properties` | object | 业务属性 |
| `risk_level` | string | 风险等级，默认 `normal` |

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
  "properties": {
    "amount": "1200万元",
    "round": "Pre-A轮"
  },
  "provenance": {
    "source_doc_id": "e2e_doc_20260528_002",
    "source_text": "端测云链科技有限公司完成Pre-A轮融资，金额1200万元。",
    "source": "extraction"
  }
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 稳定关系 ID |
| `source` | string | 起点节点 ID |
| `target` | string | 终点节点 ID |
| `type` | string | 关系类型 |
| `label` | string | 中文展示标签 |
| `confidence` | number | 置信度 |
| `status` | string | `confirmed`、`pending_review`、`rejected` |
| `properties` | object | 关系属性 |
| `provenance` | object | 证据和来源 |

## 2. 健康检查

### `GET /health`

用途：检查后端、图存储和调度器状态。

响应示例：

```json
{
  "status": "ok",
  "neo4j": "ok",
  "scheduler": "disabled"
}
```

说明：

- `neo4j=memory` 表示当前运行态使用内存图存储。
- 如果设置 `GRAPH_BACKEND=neo4j`，后端会创建 Neo4j driver 并执行连接探活；连通时返回 `neo4j=ok`，不可连时返回 `neo4j=unavailable`。
- `GRAPH_BACKEND=neo4j` 时，企业画像、子图、路径和 Text2Cypher 只读查询会走 Neo4j reader。

## 3. 数据集导入

### `POST /datasets/import`

用途：导入基础图谱数据。

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `dataset` | string | 否 | 仅支持 `financial_datasets`，默认 `financial_datasets` |

请求示例：

```json
{
  "dataset": "financial_datasets"
}
```

响应示例：

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

重复导入时，`nodes_created` 和 `relationships_created` 应下降为 0；Neo4j 模式会按真实 `MERGE` 结果返回 `nodes_skipped` 和 `relationships_skipped`。

## 4. 实时抽取

### `POST /extract`

用途：调用 LLM 从金融文本中抽取实体、关系和证据。

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `text` | string | 是 | 待抽取文本 |
| `options.self_refine` | boolean | 否 | 是否启用自修正，默认 true |
| `options.judge` | boolean | 否 | 是否启用 LLM 裁判，默认 true |
| `options.mock` | boolean | 否 | 保留兼容字段；业务运行时传 true 会返回 `400 mock_disabled` |

请求示例：

```json
{
  "text": "端测智算完成A轮融资，端测启明创投参与投资。",
  "options": {
    "self_refine": false,
    "judge": false,
    "mock": false
  }
}
```

成功响应结构：

```json
{
  "document": {
    "title": null,
    "content_hash": "hash"
  },
  "entities": [
    {
      "temp_id": "e1",
      "name": "端测智算",
      "type": "Company",
      "resolved_id": "company_xxx",
      "resolution_confidence": 0.9,
      "evidence": "端测智算完成A轮融资"
    }
  ],
  "relationships": [
    {
      "temp_id": "r1",
      "head_temp_id": "e2",
      "relation": "INVESTED_IN",
      "tail_temp_id": "e3",
      "attributes": {
        "role": "参与投资",
        "round": "A轮"
      },
      "evidence": "端测启明创投参与投资",
      "confidence": 0.9,
      "status": "confirmed"
    }
  ],
  "warnings": []
}
```

说明：抽取只走真实 LLM。未配置 LLM 时返回 `502 llm_error`；`mock=true` 返回 `400 mock_disabled`。

## 5. 抽取结果入库

### `POST /graph/import`

用途：将前端确认后的抽取结果写入图谱。

运行态说明：

- 所有导入都会先写入内存图运行态，保证当前 API 查询可立即展示。
- 当 `GRAPH_BACKEND=neo4j` 时，导入会同步调用 Neo4j writer 写穿到 Neo4j。
- Neo4j 模式下，导入响应中的新增/跳过数量来自 Neo4j 真实写入统计。

请求示例：

```json
{
  "document": {
    "title": "端到端测试新闻二",
    "content_hash": "e2e_doc_20260528_002"
  },
  "entities": [
    {
      "temp_id": "e1",
      "name": "端测云链科技有限公司",
      "type": "Company",
      "resolved_id": "company_e2e_cloudchain",
      "resolution_confidence": 0.96,
      "evidence": "端测云链科技有限公司完成Pre-A轮融资"
    },
    {
      "temp_id": "e2",
      "name": "端测高榕资本",
      "type": "Institution",
      "resolved_id": "institution_e2e_gaorong",
      "resolution_confidence": 0.96,
      "evidence": "端测高榕资本跟投"
    },
    {
      "temp_id": "e3",
      "name": "端测云链Pre-A轮融资事件",
      "type": "Event",
      "resolved_id": "event_e2e_prea",
      "resolution_confidence": 0.91,
      "evidence": "Pre-A轮融资"
    }
  ],
  "relationships": [
    {
      "temp_id": "r1",
      "head_temp_id": "e2",
      "relation": "INVESTED_IN",
      "tail_temp_id": "e3",
      "attributes": {
        "role": "跟投",
        "round": "Pre-A轮",
        "amount": "1200万元"
      },
      "evidence": "端测高榕资本跟投端测云链科技有限公司Pre-A轮融资，金额1200万元。",
      "confidence": 0.91,
      "status": "confirmed"
    },
    {
      "temp_id": "r2",
      "head_temp_id": "e1",
      "relation": "RECEIVED_FUNDING",
      "tail_temp_id": "e3",
      "attributes": {
        "round": "Pre-A轮",
        "amount": "1200万元"
      },
      "evidence": "端测云链科技有限公司完成Pre-A轮融资，金额1200万元。",
      "confidence": 0.91,
      "status": "confirmed"
    }
  ],
  "warnings": []
}
```

首次响应：

```json
{
  "nodes_created": 3,
  "nodes_matched": 0,
  "relationships_created": 2,
  "relationships_skipped": 0,
  "status": "success"
}
```

重复响应：

```json
{
  "nodes_created": 0,
  "nodes_matched": 3,
  "relationships_created": 0,
  "relationships_skipped": 2,
  "status": "success"
}
```

## 6. 企业画像

### `GET /graph/company/{name}`

查询参数：

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `depth` | number | 2 | 查询深度，服务端最多按 3 处理 |
| `include_pending` | boolean | false | 当前接口接收但未实际使用 |

请求示例：

```text
GET /graph/company/端测云链科技有限公司?depth=2
```

响应示例：

```json
{
  "company": {
    "id": "company_e2e_cloudchain",
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
  "graph": {
    "nodes": [],
    "edges": []
  }
}
```

前端重点字段：

- `company.name`
- `company.industry`
- `company.legal_representative`
- `profile.investors`
- `profile.events`
- `graph.nodes`
- `graph.edges`

## 7. 子图查询

### `GET /graph/subgraph`

查询参数：

| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `entity` | string | 是 | - | 起始实体名称 |
| `depth` | number | 否 | 2 | 查询深度 |
| `limit` | number | 否 | 80 | 最大节点/边数量 |

请求示例：

```text
GET /graph/subgraph?entity=端测云链科技有限公司&depth=2&limit=20
```

响应示例：

```json
{
  "nodes": [
    {"id": "company_e2e_cloudchain", "label": "端测云链科技有限公司", "type": "Company"}
  ],
  "edges": [
    {"id": "rel_4ce733c52a825c23", "type": "RECEIVED_FUNDING", "label": "获得融资"}
  ]
}
```

本次测试返回：`nodes=3`，`edges=2`。

## 8. 路径查询

### `GET /graph/path`

查询参数：

| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `source` | string | 是 | - | 起点实体名称 |
| `target` | string | 是 | - | 终点实体名称 |
| `max_depth` | number | 否 | 4 | 最大路径深度，内存实现最多 4 |

请求示例：

```text
GET /graph/path?source=端测高榕资本&target=端测云链科技有限公司&max_depth=3
```

响应示例：

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

## 9. GraphRAG 问答

### `POST /qa/graph-rag`

用途：基于目标实体子图调用 LLM 回答问题。

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `question` | string | 是 | 问题。建议格式：`公司名：问题内容` |

请求示例：

```json
{
  "question": "端测星河数据有限公司：它有哪些融资关系？"
}
```

真实响应核心：

```json
{
  "answer": "端测星河数据有限公司在B轮融资中获得端测红杉资本领投的3000万元融资。",
  "entities": ["端测星河数据有限公司", "端测星河数据B轮融资事件", "端测红杉资本"],
  "supporting_graph": {
    "nodes": [],
    "edges": []
  },
  "citations": [],
  "retrieval": {
    "mode": "hybrid",
    "llm_used": true,
    "answer_source": "llm"
  }
}
```

注意：该接口依赖外部 LLM，失败时返回 502。

### `POST /qa/graph-rag/stream`

用途：GraphRAG 流式问答，给前端逐字显示 AI 回答。

请求体同 `/qa/graph-rag`。

响应类型：

```text
Content-Type: text/event-stream
```

SSE 事件格式：

```text
event: metadata
data: {"supporting_graph":{"nodes":[],"edges":[]},"citations":[],"tool_calls":[{"id":"open-company-profile","label":"查看企业画像","method":"GET","endpoint":"/graph/company/端测云链科技有限公司"}],"retrieval":{"mode":"hybrid","llm_used":true,"answer_source":"llm_stream"}}

event: delta
data: {"text":"根据图谱，"}

event: delta
data: {"text":"该企业存在融资关系。"}

event: done
data: {"text":"根据图谱，该企业存在融资关系。"}
```

等待上游模型首 token 时，后端会发送心跳事件，前端可忽略或显示轻量等待态：

```text
event: ping
data: {"status":"waiting"}
```

错误事件：

```text
event: error
data: {"error":"llm_error","message":"..."}
```

`metadata.tool_calls` 结构：

```json
[
  {
    "id": "open-subgraph",
    "label": "展开关系子图",
    "description": "查看该实体 2 跳内的节点、关系和证据。",
    "method": "GET",
    "endpoint": "/graph/subgraph",
    "params": {"entity": "端测云链科技有限公司", "depth": 2, "limit": 80}
  }
]
```

## 10. Hybrid RAG

### `POST /qa/hybrid-rag`

用途：结合图谱子图和已索引文档片段进行问答。

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `question` | string | 是 | 用户问题 |
| `entity` | string | 否 | 指定图谱实体；不传时服务端从问题中抽取 |

请求示例：

```json
{
  "question": "端测云链科技有限公司：融资金额是多少？",
  "entity": "端测云链科技有限公司"
}
```

### `POST /qa/hybrid-rag/stream`

用途：Hybrid RAG 流式问答，metadata 额外包含 `document_context`。

请求体同 `/qa/hybrid-rag`。

SSE 事件同 `/qa/graph-rag/stream`：

- `metadata`
- `ping`
- `delta`
- `done`
- `error`

真实响应核心：

```json
{
  "answer": "端测云链科技有限公司的融资金额是1200万元。",
  "retrieval": {
    "graph_nodes": 3,
    "graph_edges": 2,
    "document_chunks": 2,
    "llm_used": true,
    "answer_source": "llm"
  },
  "citations": [
    {
      "source_text": "端测云链科技有限公司完成Pre-A轮融资，金额1200万元。"
    }
  ]
}
```

## 11. Text2Cypher

### `POST /qa/text2cypher`

用途：把中文问题转为只读 Cypher，并返回表格和图结构。

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `question` | string | 是 | 中文查询问题 |

安全拒绝示例：

```json
{
  "question": "删除所有节点"
}
```

响应：

```json
{
  "error": "unsafe_cypher",
  "message": "生成的 Cypher 包含写操作意图，已拒绝执行。",
  "cypher": ""
}
```

状态码：`400`

读查询成功结构：

```json
{
  "cypher": "MATCH (c:Company) RETURN c LIMIT 50",
  "safety": {
    "passed": true,
    "rules": ["read_only", "path_depth_checked", "schema_checked", "limit_added"]
  },
  "table": {
    "columns": [],
    "rows": []
  },
  "graph": {
    "nodes": [],
    "edges": []
  }
}
```

说明：Text2Cypher 会拒绝写操作、过深路径、超大 LIMIT，以及不在项目 schema 白名单中的 label 或关系类型。LLM 返回带 Markdown 代码块或前后缀说明的 JSON 时，后端会提取第一个 JSON object 后再校验。

LLM 不可用响应：

```json
{
  "detail": {
    "error": "llm_error",
    "message": "OPENAI_API_KEY is required for LLM calls."
  }
}
```

## 12. RAG 文档索引

### `POST /rag/documents`

用途：向内存向量检索模块写入文档片段。

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `doc_id` | string | 是 | 文档 ID |
| `title` | string | 否 | 标题 |
| `text` | string | 是 | 正文 |
| `metadata` | object | 否 | 来源、日期等 |

请求示例：

```json
{
  "doc_id": "e2e_doc_20260528_002",
  "title": "端测云链融资新闻",
  "text": "端测云链科技有限公司完成Pre-A轮融资，端测高榕资本跟投，融资金额1200万元。",
  "metadata": {
    "source": "e2e",
    "pub_date": "2026-05-28"
  }
}
```

响应示例：

```json
{
  "doc_id": "e2e_doc_20260528_002",
  "chunks_indexed": 1,
  "status": "success"
}
```

## 13. 定时任务

### `GET /jobs`

用途：查看最近任务运行记录。

响应示例：

```json
{
  "jobs": []
}
```

### `POST /jobs/akshare/run`

用途：手动触发 AKShare 新闻抓取、抽取、裁判、入库 Pipeline。

成功响应结构：

```json
{
  "job_run_id": "job_20260528_153000",
  "status": "success",
  "started_at": "2026-05-28T15:30:00",
  "finished_at": "2026-05-28T15:30:20",
  "new_documents": 10,
  "new_entities": 3,
  "new_relationships": 2,
  "failed_items": 0
}
```

说明：该接口调用真实 AKShare fetcher 和真实 LLM extraction pipeline。外部源或 LLM 不可用时，任务会记录 `failed_items`，不会读取本地快照样例或生成假关系。

### `GET /jobs/{job_run_id}`

用途：查看单次任务详情。

错误响应：

```json
{
  "detail": {
    "error": "scheduler_error",
    "message": "job run not found"
  }
}
```

状态码：`404`

## 14. 质量评测

### `GET /metrics/extraction`

### `POST /metrics/evaluate`

用途：用 `data/gold/gold_standard.json` 计算抽取指标。

真实响应核心：

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

说明：接口需要配置真实 predictor；未配置时返回 `503 metrics_unavailable`，避免把规则 baseline 当成最终 LLM 指标。

## 15. 股票研判

### `POST /analysis/stock`

用途：基于图谱、基本面占位字段和消息事件生成结构化研判。

请求参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `stock_code` | string | 是 | 股票代码 |
| `company_name` | string | 否 | 公司名 |
| `depth` | number | 否 | 图谱召回深度，默认 2 |
| `news_window_days` | number | 否 | 新闻窗口 |
| `refresh_news` | boolean | 否 | 是否补充实时新闻 |
| `use_llm` | boolean | 否 | 是否调用 LLM 生成结构化研判，默认 false；默认返回本地结构化摘要，避免前端等待 |

请求示例：

```json
{
  "stock_code": "600000",
  "company_name": "端测星河数据有限公司",
  "depth": 2,
  "news_window_days": 30,
  "refresh_news": false
}
```

成功响应结构：

```json
{
  "target": {
    "stock_code": "600000",
    "company_name": "端测星河数据有限公司"
  },
  "fundamentals": {
    "stock_code": "600000",
    "company_name": "端测星河数据有限公司",
    "industry": "未知",
    "data_time": "local-cache"
  },
  "news_events": [],
  "subgraph": {
    "nodes": [],
    "edges": []
  },
  "analysis": {
    "summary": "结构化研判摘要",
    "opportunity_factors": [],
    "risk_factors": [],
    "graph_insights": [],
    "confidence": 0.75,
    "missing_data": [],
    "disclaimer": "本结果仅用于课程项目演示和研究辅助，不构成投资建议。"
  }
}
```

说明：接口默认不等待 LLM，直接返回本地图谱摘要和结构化字段。需要模型生成结构化研判时传 `use_llm=true`；如果模型不可用，会保留本地摘要，并在 `analysis.missing_data` 中追加“模型研判暂不可用，已返回本地图谱摘要：...”。

### `GET /analysis/stock/{stock_code}/latest`

用途：设计上应返回最近一次研判。

当前实现行为：优先返回进程内最近一次该股票研判缓存；没有缓存时返回本地图谱摘要，不触发 LLM。

### `POST /analysis/stock/stream`

用途：股票研判流式文本输出，适合前端研判卡片逐步显示。

请求体同 `/analysis/stock`。

响应类型：

```text
Content-Type: text/event-stream
```

SSE 事件：

- `metadata`：返回 `target`、`fundamentals`、`news_events`、`subgraph`、`tool_calls`。
- `ping`：等待上游 token 时的心跳。
- `delta`：逐段返回研判文本。
- `done`：返回完整文本。
- `error`：返回 LLM 错误。

注意：流式接口输出的是展示文本，不是结构化 JSON；需要结构化字段时继续调用 `/analysis/stock`。

## 16. K 线行情

### `GET /market/kline/{stock_code}`

查询参数：

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `market` | string | `A` | 市场 |
| `period` | string | `daily` | 周期 |
| `start_date` | string | 近 180 天 | 起始日期 |
| `end_date` | string | 当前日期 | 结束日期 |
| `adjust` | string | `qfq` | 复权方式 |

请求示例：

```text
GET /market/kline/600000?market=A&period=daily&start_date=2024-01-01&end_date=2024-01-10&adjust=qfq
```

真实响应核心：

```json
{
  "stock_code": "600000",
  "market": "A",
  "display_code": "600000.SH",
  "company_name": "600000",
  "period": "daily",
  "adjust": "qfq",
  "cached": false,
  "data_source": "yfinance",
  "start_date": "2024-01-01",
  "end_date": "2024-01-10",
  "kline_data": [
    {
      "date": "2024-01-02",
      "open": 7.23,
      "close": 7.45,
      "high": 7.5,
      "low": 7.18,
      "volume": 123,
      "amount": 456.7
    }
  ],
  "events": []
}
```

说明：行情优先来自 yfinance；yfinance 不可用时会请求 Yahoo Chart 作为第二真实源，仍不可用时再尝试 AKShare。成功时 `data_source` 可能是 `yfinance`、`yahoo_chart` 或 `akshare`。同参请求在 `MARKET_KLINE_CACHE_TTL_SECONDS` 内复用缓存并返回 `cached=true`；配置 `MARKET_KLINE_CACHE_DIR` 后，进程重启后也能从磁盘缓存恢复。缓存过期后如果三个真实源都失败，会返回最近一次真实缓存并标记 `cache_status=stale_if_error`；没有可用真实缓存时返回 `503 market_data_error`，不返回 mock K 线。

## 17. 错误格式

### LLM 错误

```json
{
  "detail": {
    "error": "llm_error",
    "message": "The read operation timed out"
  }
}
```

状态码：`502`

### Text2Cypher 安全错误

```json
{
  "error": "unsafe_cypher",
  "message": "生成的 Cypher 包含写操作意图，已拒绝执行。",
  "cypher": ""
}
```

状态码：`400`

### Job 不存在

```json
{
  "detail": {
    "error": "scheduler_error",
    "message": "job run not found"
  }
}
```

状态码：`404`
