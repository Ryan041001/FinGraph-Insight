# 05 LLM 抽取与质量评测

## 1. 抽取目标

从金融新闻、公告、专栏文本中抽取：

- 实体：公司、人物、投资机构、事件、行业。
- 关系：投资、融资、持股、任职、合作、竞争、子公司、共同地址、共同法人等。
- 属性：金额、轮次、日期、职位、持股比例、证据文本。

## 2. 抽取策略

采用“schema 约束 + 两阶段抽取 + 自修正 + 裁判验证”。

### 2.1 Stage 1：关系类型识别

输入文本和允许的关系类型，让模型先判断文本中可能存在的关系类型，缩小搜索空间。

### 2.2 Stage 2：实体对和属性抽取

针对每种关系类型，要求模型输出实体对、实体类型、关系属性和证据片段。

### 2.3 自修正

模型抽取后再检查：

- 是否遗漏实体。
- 实体类型是否错误。
- 关系方向是否反。
- 是否有原文不支持的幻觉关系。

最多迭代 2 到 3 轮，避免调用成本和延迟失控。

### 2.4 LLM 裁判

对每条三元组打分：

- `1.0`：原文明确支持。
- `0.8`：原文强烈暗示。
- `0.5`：有一定依据但不确定。
- `0.2`：依据很弱。
- `0.0`：原文不支持。

入库策略：

- `confidence >= 0.8`：confirmed。
- `0.5 <= confidence < 0.8`：pending_review。
- `confidence < 0.5`：rejected，不入库。

## 3. 结构化输出约束

后端必须用 Pydantic 校验 LLM 输出，不允许直接信任模型返回。

建议结构：

```json
{
  "entities": [
    {
      "name": "红杉资本",
      "type": "Institution",
      "normalized_name": "红杉资本",
      "evidence": "红杉资本领投",
      "start": 0,
      "end": 4
    }
  ],
  "relationships": [
    {
      "head": "红杉资本",
      "head_type": "Institution",
      "relation": "INVESTED_IN",
      "tail": "某科技公司B轮融资",
      "tail_type": "Event",
      "attributes": {
        "round": "B轮",
        "amount": "3000万",
        "role": "领投"
      },
      "evidence": "红杉资本领投了该公司B轮融资",
      "confidence": 0.92
    }
  ]
}
```

校验失败处理：

1. 尝试 JSON 修复。
2. 再次请求模型按 schema 输出。
3. 仍失败则记录到 rejected 日志。

## 4. 领域知识增强

抽取前注入：

- 已有公司和机构名称。
- 实体别名。
- 关系类型说明。
- 错误模式。

错误模式示例：

- “A 轮融资”是事件，不是公司。
- “估值 10 亿”不是融资金额。
- “领投”和“跟投”是投资角色，不是不同关系类型。
- “控股”和“参股”含义不同。

## 5. 金标准评测集

P0 要求至少 50 条样本，建议结构：

```json
[
  {
    "id": "gold_001",
    "text": "红杉资本领投了某科技公司B轮融资，融资金额为3000万元。",
    "entities": [
      {"name": "红杉资本", "type": "Institution"},
      {"name": "某科技公司", "type": "Company"},
      {"name": "B轮融资", "type": "Event"}
    ],
    "relationships": [
      {
        "head": "红杉资本",
        "relation": "INVESTED_IN",
        "tail": "B轮融资",
        "attributes": {"role": "领投", "amount": "3000万元"}
      },
      {
        "head": "某科技公司",
        "relation": "RECEIVED_FUNDING",
        "tail": "B轮融资"
      }
    ]
  }
]
```

## 6. 实验分组

| 实验组 | 方法 | 目标 |
| --- | --- | --- |
| Baseline 1 | 单轮 prompt | 基础效果 |
| Baseline 2 | ChatIE 两阶段 | 验证两阶段抽取收益 |
| Method 1 | 两阶段 + 实体词典 | 验证领域知识 |
| Method 2 | 两阶段 + 自修正 | 验证迭代修正 |
| Method 3 | 两阶段 + 自修正 + 裁判过滤 | 最终方案 |

## 7. 指标

必须统计：

- 实体 Precision / Recall / F1。
- 关系 Precision / Recall / F1。
- 幻觉率：原文不支持的关系比例。
- 有效入库率：通过置信度阈值的关系比例。
- 平均抽取耗时。

可选统计：

- 每类关系 F1。
- 不同文本长度下的表现。
- 自修正前后差异。

## 8. 测试命令

建议：

```text
pytest backend/tests/test_extraction.py
```

测试内容：

- 输出 JSON 合法性。
- schema 枚举合法性。
- 实体消歧正确性。
- gold set 指标计算。
- 低置信度关系不会入库。
