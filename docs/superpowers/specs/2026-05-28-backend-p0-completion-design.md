# Backend P0 Completion Design

## Goal

补齐后端“知识图谱 + 大模型应用”的最后一公里能力：自动化抽取入库 Pipeline、最小可用 Hybrid RAG、真实金标准评测、基础实体消歧增强，以及内存/Neo4j 导入路径收口。

## Current Evidence

- FastAPI 路由、LLM 网关、图查询、Text2Cypher、K 线和智能研判接口已经存在。
- `data/gold/gold_standard.json` 已有 50 条样本，但内容存在乱码风险，`metrics_service.py` 当前只返回固定满分基线。
- `scheduler_service.py` 已能抓取 AKShare 新闻并记录 job，但未执行抽取、裁判、入库。
- `graph_rag_service.py` 只使用图谱子图，没有文档 chunk 或向量召回。
- `entity_resolution_service.py` 有归一化和别名匹配，但没有候选消歧和模糊匹配。
- Neo4j writer 和 runtime 存在，但 `/graph/import` 没有走 runtime，查询仍依赖内存图。

## Scope

### 1. Entity Resolution

`EntityResolver` 增强为可注册候选实体的 resolver：

- 精确匹配：原名完全一致。
- 归一化匹配：去空白、全角半角归一、去公司后缀。
- 别名匹配：显式 alias 映射到标准名。
- 模糊匹配：使用标准库 `difflib.SequenceMatcher`，返回 `candidates` 和置信度。

抽取结果归一化时接入 resolver，写入 `resolved_name`、`resolved_id`、`resolution_confidence`、`resolution_match_type`。

### 2. Document Vector Store and Hybrid RAG

不引入外部向量库依赖，先实现可测试、可演示的轻量向量检索：

- `HashingEmbeddingProvider`：基于中文字符 bigram/trigram 和英文 token 生成固定维度向量。
- `InMemoryVectorStore`：保存文档 chunk、metadata、embedding，支持 cosine top-k。
- `index_document()`：清洗和分块后入库。
- `answer_with_hybrid_context()`：融合图谱子图和向量 chunk，返回 `document_context`、`retrieval`、`citations`。

该设计保留向 ChromaDB/FAISS 替换的边界，但当前实现无需网络下载和额外服务。

### 3. Automated Update Pipeline

新增 `pipeline_service.py`，把已有服务串成自动化工作流：

1. fetcher 获取文档。
2. 文档清洗、chunk、向量索引。
3. 对每篇文档调用 extractor。
4. 可选 judge。
5. `confidence >= 0.8` 的关系自动入库，`0.5 <= confidence < 0.8` 保留 pending 但默认不自动写入。
6. 记录 `new_documents`、`new_entities`、`new_relationships`、`failed_items`。

`scheduler_service.py` 改为调用 pipeline，并用 APScheduler 在 FastAPI lifespan 中按配置启动周期任务。手动接口继续使用 `POST /jobs/akshare/run`。

### 4. Real Metrics

`evaluate_gold_standard()` 不再返回固定满分，而是支持预测函数：

- 默认使用本地规则抽取作为 baseline，保证无 LLM key 也能运行。
- 实体按 `(normalized_name, type)` 计算 P/R/F1。
- 关系按 `(normalized_head, relation, normalized_tail)` 计算 P/R/F1。
- 幻觉率 = 预测中不在 gold 的关系数 / 预测关系数。
- 有效入库率 = `confirmed` 关系数 / 预测关系数。
- 返回 `sample_count`、各项指标、`per_sample` 摘要。

同时修复 gold set 编码内容，使评测样本是可读中文。

### 5. Graph Runtime

新增 extraction payload 到 GraphPayload 的转换函数，并让 `/graph/import` 与 pipeline 都走 runtime：

- memory graph 始终保持查询可用。
- 当 `GRAPH_BACKEND=neo4j` 时，runtime 同步写 Neo4j。
- 写入统计继续保持现有 API 契约。

## Non-Goals

- 不实现复杂 Agent planning/reasoning 框架。
- 不接入真实在线 embedding API。
- 不把所有图查询迁移为 Neo4j Cypher 查询；本轮只修复写通路径和演示一致性。

## Testing Strategy

- 先写失败测试覆盖 resolver 候选匹配、向量检索、Hybrid RAG、pipeline 入库统计、真实 metrics、runtime 写通。
- 每组测试 RED 后实现最小代码，再跑对应测试 GREEN。
- 最后运行 `uv run pytest` 验证后端全量测试。
