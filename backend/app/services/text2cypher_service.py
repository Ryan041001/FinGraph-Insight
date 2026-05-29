import re

from app.models.api import Text2CypherResponse, Text2CypherSafety
from app.services.llm_service import LLMGateway, LLMTask
from app.services.llm_json import parse_llm_json_object, require_llm_json_string
from app.models.api import GraphPayload
from app.services.graph_store import graph_store


DEFAULT_LIMIT = 50
MAX_LIMIT = 100
MAX_PATH_DEPTH = 3

FORBIDDEN_KEYWORDS = {
    "CREATE",
    "MERGE",
    "DELETE",
    "DETACH DELETE",
    "SET",
    "REMOVE",
    "DROP",
    "LOAD CSV",
    "CALL DBMS",
    "CALL APOC",
}

ALLOWED_LABELS = {"Company", "Person", "Institution", "Event", "Industry", "Document"}
ALLOWED_RELATIONSHIPS = {
    "INVESTED_IN",
    "RECEIVED_FUNDING",
    "HOLDS_SHARES",
    "LEGAL_REP_OF",
    "EXECUTIVE_OF",
}


def is_write_intent(question: str) -> bool:
    write_words = ("删除", "创建", "修改", "更新", "清空", "写入")
    return any(word in question for word in write_words)


def validate_cypher(cypher: str) -> tuple[bool, str | None]:
    upper = _strip_comments(cypher).upper()
    for keyword in FORBIDDEN_KEYWORDS:
        pattern = r"\b" + r"\s+".join(re.escape(part) for part in keyword.split()) + r"\b"
        if re.search(pattern, upper):
            return False, f"生成的 Cypher 包含写操作关键词 {keyword}，已拒绝执行。"
    return True, None


def sanitize_readonly_cypher(
    cypher: str,
    *,
    extra_labels: set[str] | None = None,
    extra_relationships: set[str] | None = None,
) -> tuple[str, list[str]]:
    cleaned = _strip_comments(cypher).strip().rstrip(";")
    upper = cleaned.upper()
    rules = ["read_only"]

    passed, reason = validate_cypher(cleaned)
    if not passed:
        raise ValueError(reason)

    if not upper.startswith(("MATCH ", "OPTIONAL MATCH ")):
        raise ValueError("生成的 Cypher 不是只读 MATCH 查询，已拒绝执行。")

    _validate_path_depth(cleaned)
    rules.append("path_depth_checked")
    _validate_schema_tokens(
        cleaned,
        extra_labels=extra_labels or set(),
        extra_relationships=extra_relationships or set(),
    )
    rules.append("schema_checked")

    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", cleaned, flags=re.IGNORECASE)
    if limit_match is None:
        return f"{cleaned} LIMIT {DEFAULT_LIMIT}", [*rules, "limit_added"]

    limit_value = int(limit_match.group(1))
    if limit_value > MAX_LIMIT:
        capped = re.sub(
            r"\bLIMIT\s+\d+\b",
            f"LIMIT {MAX_LIMIT}",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )
        return capped, [*rules, "limit_capped"]

    return cleaned, [*rules, "limit_checked"]


def answer_text2cypher(question: str) -> Text2CypherResponse:
    if is_write_intent(question):
        raise ValueError("生成的 Cypher 包含写操作意图，已拒绝执行。")

    cypher, safety_rules = sanitize_readonly_cypher("MATCH (c:Company)-[r]-(n) RETURN c, r, n")

    return Text2CypherResponse(
        cypher=cypher,
        safety=Text2CypherSafety(passed=True, rules=safety_rules),
        table={"columns": [], "rows": []},
        graph=GraphPayload(nodes=[], edges=[]),
    )


def generate_cypher_with_llm(question: str, gateway: LLMGateway) -> tuple[str, list[str]]:
    runtime_labels, runtime_relationships = _runtime_schema_tokens()
    allowed_labels = sorted(ALLOWED_LABELS | runtime_labels)
    allowed_relationships = sorted(ALLOWED_RELATIONSHIPS | runtime_relationships)
    schema_hint = (
        f"图谱节点标签只能使用：{', '.join(allowed_labels)}。"
        f"关系类型只能使用：{', '.join(allowed_relationships)}。"
        "实体语义：投资方/投资机构/资本是 Institution（不是 Person）；被投/融资企业是 Company；"
        "融资轮次/事件是 Event。"
        "关系模式（务必匹配端点类型与方向）："
        "(Institution)-[:INVESTED_IN]->(Event)；(Company)-[:RECEIVED_FUNDING]->(Event)；"
        "(Institution)-[:HOLDS_SHARES]->(Company)；(Person)-[:LEGAL_REP_OF]->(Company)；"
        "(Person)-[:EXECUTIVE_OF]->(Company)。"
        "查‘某公司的投资方’应经事件桥接："
        "(c:Company)-[:RECEIVED_FUNDING]->(:Event)<-[:INVESTED_IN]-(inv:Institution)，返回 inv。"
        "不要把投资方建模成 Person，也不要在 Company 与 Institution 之间直接连 INVESTED_IN。"
        "若问题需要的关系不在列表中，请用最接近的合法关系并保持上述端点类型与方向。"
    )
    content = gateway.complete(
        task=LLMTask.TEXT2CYPHER,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是 Neo4j Cypher 生成器。请输出 json，格式为 {\"cypher\": \"...\"}。"
                    "只能生成只读 MATCH/OPTIONAL MATCH 查询，不允许 CREATE、MERGE、SET、DELETE、CALL、LOAD CSV。"
                    f"最大路径深度为 {MAX_PATH_DEPTH}，查询必须可追加或包含 LIMIT {DEFAULT_LIMIT}。"
                    f"\n{schema_hint}"
                ),
            },
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=1024,
    )
    payload = parse_llm_json_object(content)
    return sanitize_readonly_cypher(
        require_llm_json_string(payload, "cypher"),
        extra_labels=runtime_labels,
        extra_relationships=runtime_relationships,
    )


def _strip_comments(cypher: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", " ", cypher, flags=re.DOTALL)
    return re.sub(r"//.*?$", "", without_block_comments, flags=re.MULTILINE)


def _validate_path_depth(cypher: str) -> None:
    for match in re.finditer(r"\*\s*(\d+)?\s*\.\.\s*(\d+)", cypher):
        upper_bound = int(match.group(2))
        if upper_bound > MAX_PATH_DEPTH:
            raise ValueError(f"生成的 Cypher 路径深度超过 {MAX_PATH_DEPTH}，已拒绝执行。")


def _validate_schema_tokens(
    cypher: str,
    *,
    extra_labels: set[str],
    extra_relationships: set[str],
) -> None:
    allowed_labels = ALLOWED_LABELS | extra_labels
    allowed_relationships = ALLOWED_RELATIONSHIPS | extra_relationships
    labels = set(re.findall(r":\s*([A-Za-z_][A-Za-z0-9_]*)", _strip_relationship_patterns(cypher)))
    unknown_labels = sorted(labels - allowed_labels)
    if unknown_labels:
        raise ValueError(f"生成的 Cypher 包含未知图谱标签 {', '.join(unknown_labels)}，已拒绝执行。")

    relationships = set(re.findall(r"\[\s*\w*\s*:\s*([A-Za-z_][A-Za-z0-9_]*)", cypher))
    unknown_relationships = sorted(relationships - allowed_relationships)
    if unknown_relationships:
        raise ValueError(f"生成的 Cypher 包含未知关系类型 {', '.join(unknown_relationships)}，已拒绝执行。")


def _strip_relationship_patterns(cypher: str) -> str:
    return re.sub(r"\[[^\]]*\]", " ", cypher)


def _runtime_schema_tokens() -> tuple[set[str], set[str]]:
    try:
        labels, relationships = graph_store.schema_tokens()
    except AttributeError:
        return set(), set()
    return set(labels), set(relationships)
