# 04 技术架构与 Pipeline

## 1. 总体架构

详细工程落地方案见 [09_工程层_详细架构落地方案.md](09_工程层_详细架构落地方案.md)，本文件保留整体架构和 Pipeline 说明。

```text
数据源
  |-- FinancialDatasets
  |-- AKShare
  |-- 新闻/公告文本
        |
        v
数据处理层
  |-- 清洗
  |-- 分块
  |-- 字段映射
  |-- 实体消歧
        |
        v
抽取与验证层
  |-- LLM 抽取
  |-- Pydantic 校验
  |-- 自修正
  |-- LLM 裁判
  |-- 置信度过滤
        |
        v
图谱存储层
  |-- Neo4j
  |-- 约束和索引
  |-- 幂等写入
        |
        v
应用层
  |-- 企业画像
  |-- 图谱浏览
  |-- GraphRAG
  |-- Text2Cypher
  |-- 定时更新
```

## 2. 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue3 + Vite + Element Plus |
| 图谱可视化 | ECharts Graph 或 vis-network |
| 后端 | FastAPI |
| 大模型接口 | OpenAI SDK 兼容接口，可接 DeepSeek/Qwen/GLM |
| 图数据库 | Neo4j Community Edition 5.x |
| 数据处理 | pandas + openpyxl + BeautifulSoup |
| 定时任务 | APScheduler |
| 向量检索 | ChromaDB 或 FAISS，P1 可做 |
| 部署 | Docker Compose |

## 3. 后端模块

建议目录：

```text
backend/
  main.py
  config.py
  models/
    extraction_schema.py
    graph_schema.py
  services/
    extraction.py
    entity_resolution.py
    self_refine.py
    judge.py
    graph_rag.py
    text2cypher.py
    scheduler.py
  neo4j/
    connection.py
    constraints.py
    queries.py
    writer.py
  data/
    loader.py
    preprocessor.py
    akshare_fetcher.py
  tests/
    gold_standard.json
    test_extraction.py
```

## 4. 基础图谱构建 Pipeline

1. 下载 FinancialDatasets。
2. 用 pandas 读取 xlsx。
3. 清洗字段、去重、归一化实体名称。
4. 生成节点表：
   - Company
   - Institution
   - Person
   - Event
   - Industry
   - Document
5. 生成关系表：
   - 投资关系
   - 融资关系
   - 法人关系
   - 行业关系
   - 共同地址和共同法人关系
6. 写入 Neo4j。
7. 记录导入日志。

## 5. LLM 抽取 Pipeline

1. 接收文本。
2. 清洗 HTML 和异常字符。
3. 分句和分块。
4. 检索领域词典和 schema 约束。
5. LLM 抽取实体和关系。
6. Pydantic 校验输出。
7. 自修正和重试。
8. 实体消歧。
9. LLM 裁判打分。
10. 置信度过滤。
11. 前端展示或写入 Neo4j。

## 6. 定时更新 Pipeline

定时更新保留为 P0 功能。

### 6.1 调度方式

- 使用 APScheduler。
- 默认每 6 小时执行一次，开发阶段可改为每小时。
- 提供后端接口手动触发。
- 每次任务有唯一 `job_run_id`。

### 6.2 更新内容

P0：

- AKShare 股票新闻。
- AKShare 主要股东或流通股东数据。

P1：

- 公告数据。
- Tushare 补充字段。

### 6.3 幂等与失败处理

- 抓取结果先保存快照。
- 根据 `content_hash` 判断新闻是否已处理。
- 根据稳定关系 ID 避免重复写入。
- 任务失败不影响主服务启动。
- 失败原因写入更新日志，前端可查看。

### 6.4 手动兜底

前端提供“立即更新”按钮，调用：

```text
POST /jobs/akshare/run
```

返回：

```json
{
  "job_run_id": "20260527_001",
  "status": "success",
  "new_documents": 12,
  "new_entities": 8,
  "new_relationships": 15,
  "failed_items": 1
}
```

## 7. 冲突处理

冲突类型：

- 同一关系来自多个来源，置信度不同。
- 股权比例发生变化。
- 同一实体被识别为不同类型。

处理规则：

- 结构化数据优先级高于 LLM 抽取。
- 新数据只覆盖当前有效关系，不删除历史关系。
- 股权比例变化时，旧关系设置 `valid_to`，新关系设置新的 `valid_from`。
- 低置信度关系进入 `pending_review` 状态。

## 8. Docker Compose 服务

建议服务：

```text
services:
  neo4j:
    image: neo4j:5
  backend:
    build: ./backend
    depends_on:
      - neo4j
  frontend:
    build: ./frontend
    depends_on:
      - backend
```

必须提供：

- `.env.example`
- `README.md`
- Neo4j 初始化约束脚本
- 样例数据导入命令
