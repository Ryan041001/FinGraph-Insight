# 03 数据与图谱 Schema

## 1. 数据来源

| 数据层 | 来源 | 用途 | 是否 P0 |
| --- | --- | --- | --- |
| 静态基础数据 | FinancialDatasets | 构建公司、机构、投资事件和新闻语料 | 是 |
| 动态结构化数据 | AKShare | 股东、新闻、公告等增量更新 | 是 |
| 补充结构化数据 | Tushare Pro | 前十大股东、质押、增减持 | 否 |
| 深度文档 | 巨潮资讯公告 PDF | 复杂文档抽取演示 | 否 |

## 2. 数据目录规范

建议目录：

```text
data/
  raw/
    FinancialDatasets/
    akshare_snapshots/
  interim/
    cleaned_tables/
    text_chunks/
  processed/
    nodes/
    relationships/
    import_logs/
  gold/
    gold_standard.json
```

规则：

- `raw/` 只保存原始下载数据，不手工修改。
- `interim/` 保存清洗后的中间产物。
- `processed/` 保存可直接入库的节点和关系。
- `gold/` 保存人工标注评测集。
- 所有脚本必须支持重复执行。

## 3. 数据预处理

### 3.1 通用规则

- 去除空行、重复行和明显无效字段。
- 公司名、机构名统一做全角半角、空格、括号和后缀归一化。
- 日期统一为 `YYYY-MM-DD`。
- 金额保留原文，同时尽量解析为标准数值字段。
- 新闻正文先用 BeautifulSoup 去除 HTML 标签。
- 长文本按句子切分后再分块。

### 3.2 文本分块

默认策略：

- 最大长度：约 512 tokens。
- overlap：20%。
- 分块单位：句子优先，避免从实体中间截断。
- 每个 chunk 生成稳定 `chunk_id`。

## 4. 实体消歧

实体消歧是图谱质量的关键模块，建议实现 `entity_resolution.py`。

优先级：

1. 公司有统一社会信用代码时，以信用代码为主键。
2. 无信用代码时，使用归一化名称。
3. 名称相近时，结合地址、法人、行业、网址辅助判断。
4. 投资机构维护 alias 表，例如简称、英文名、历史名。
5. LLM 抽取的新实体默认先进入候选状态，入库前做实体链接。

输出字段：

```json
{
  "input_name": "蚂蚁金服",
  "resolved_id": "company_ant_group",
  "resolved_name": "蚂蚁科技集团股份有限公司",
  "match_type": "alias",
  "confidence": 0.95
}
```

## 5. 节点 Schema

| 标签 | 核心属性 | 来源 |
| --- | --- | --- |
| `Company` | id, name, full_name, aliases, industry, registered_capital, address, legal_representative, credit_code, status | 工商数据、AKShare、LLM |
| `Person` | id, name, title, gender | 工商数据、新闻抽取 |
| `Institution` | id, name, aliases, type, industry_preference, investment_stage, scale | 投资机构数据 |
| `Event` | id, name, event_type, date, amount, round, description | 投资事件、新闻抽取 |
| `Industry` | id, name, level | 行业字段 |
| `Document` | id, title, source, url, pub_date, content_hash | 新闻、公告、数据文件 |

## 6. 关系 Schema

上市公司节点可额外带以下可选属性：

| 字段 | 说明 |
| --- | --- |
| `stock_code` | 调行情接口使用的纯代码，如 `600000` |
| `display_code` | 前端展示代码，如 `600000.SH` |
| `market` | `A` 或 `HK` |
| `exchange` | `SSE`、`SZSE`、`HKEX` |
| `listed` | 是否上市公司 |

| 关系 | 起点到终点 | 属性 |
| --- | --- | --- |
| `INVESTED_IN` | Institution/Company -> Event | amount, round, role |
| `RECEIVED_FUNDING` | Company -> Event | amount, round |
| `HOLDS_SHARES` | Company/Person -> Company | ratio, share_count, valid_from, valid_to |
| `LEGAL_REP_OF` | Person -> Company | valid_from, valid_to |
| `EXECUTIVE_OF` | Person -> Company | title, valid_from, valid_to |
| `COOPERATES_WITH` | Company -> Company | type, date, description |
| `COMPETES_WITH` | Company -> Company | industry |
| `SUBSIDIARY_OF` | Company -> Company | ratio |
| `SAME_ADDRESS` | Company -> Company | address |
| `SAME_LEGAL_REP` | Company -> Company | person_name |
| `BELONGS_TO` | Company -> Industry | source |
| `MENTIONED_IN` | Company/Person/Institution/Event -> Document | chunk_id, evidence_span |

## 7. 关系元属性

每条关系至少包含：

```json
{
  "id": "rel_hash",
  "confidence": 0.92,
  "source": "36kr_news.xlsx",
  "source_doc_id": "doc_hash",
  "source_text": "红杉资本领投了该公司B轮融资...",
  "chunk_id": "doc_hash_0003",
  "extraction_time": "2026-05-27T20:00:00",
  "model": "deepseek-v3",
  "valid_from": "2023-04-15",
  "valid_to": null,
  "schema_version": "v1",
  "status": "confirmed"
}
```

## 8. 稳定 ID 设计

建议：

- `Company.id = hash(credit_code)`；无信用代码时用 `hash(normalized_name + address)`。
- `Institution.id = hash(normalized_name)`。
- `Person.id = hash(name + related_company_id)`，避免同名人物直接合并。
- `Event.id = hash(event_type + date + main_participants + amount)`。
- `Document.id = hash(source + title + pub_date)`。
- `Relation.id = hash(head_id + relation_type + tail_id + source_doc_id + valid_from)`。

## 9. Neo4j 约束和索引

初始化时建议执行：

```cypher
CREATE CONSTRAINT company_id IF NOT EXISTS
FOR (n:Company) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT institution_id IF NOT EXISTS
FOR (n:Institution) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT person_id IF NOT EXISTS
FOR (n:Person) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT event_id IF NOT EXISTS
FOR (n:Event) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT document_id IF NOT EXISTS
FOR (n:Document) REQUIRE n.id IS UNIQUE;

CREATE INDEX company_name IF NOT EXISTS
FOR (n:Company) ON (n.name);

CREATE INDEX institution_name IF NOT EXISTS
FOR (n:Institution) ON (n.name);
```

写入方式：

- 节点使用 `MERGE`。
- 关系先计算稳定 `id`，再 `MERGE`。
- 动态更新时，旧关系失效要设置 `valid_to`，新关系另建一条。
