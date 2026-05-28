import re

from app.models.api import Text2CypherResponse, Text2CypherSafety
from app.services.llm_service import LLMGateway, LLMTask
from app.services.llm_json import parse_llm_json_object, require_llm_json_string
from app.models.api import GraphPayload


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
        if keyword in upper:
            return False, f"生成的 Cypher 包含写操作关键词 {keyword}，已拒绝执行。"
    return True, None


def sanitize_readonly_cypher(cypher: str) -> tuple[str, list[str]]:
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
    _validate_schema_tokens(cleaned)
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
    content = gateway.complete(
        task=LLMTask.TEXT2CYPHER,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是 Neo4j Cypher 生成器。请输出 json，格式为 {\"cypher\": \"...\"}。"
                    "只能生成只读 MATCH/OPTIONAL MATCH 查询，不允许 CREATE、MERGE、SET、DELETE、CALL、LOAD CSV。"
                    "最大路径深度为 3，查询必须可追加或包含 LIMIT。"
                ),
            },
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=1024,
    )
    payload = parse_llm_json_object(content)
    return sanitize_readonly_cypher(require_llm_json_string(payload, "cypher"))


def _strip_comments(cypher: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", " ", cypher, flags=re.DOTALL)
    return re.sub(r"//.*?$", "", without_block_comments, flags=re.MULTILINE)


def _validate_path_depth(cypher: str) -> None:
    for match in re.finditer(r"\*\s*(\d+)?\s*\.\.\s*(\d+)", cypher):
        upper_bound = int(match.group(2))
        if upper_bound > MAX_PATH_DEPTH:
            raise ValueError(f"生成的 Cypher 路径深度超过 {MAX_PATH_DEPTH}，已拒绝执行。")


def _validate_schema_tokens(cypher: str) -> None:
    labels = set(re.findall(r":\s*([A-Za-z_][A-Za-z0-9_]*)", _strip_relationship_patterns(cypher)))
    unknown_labels = sorted(labels - ALLOWED_LABELS)
    if unknown_labels:
        raise ValueError(f"生成的 Cypher 包含未知图谱标签 {', '.join(unknown_labels)}，已拒绝执行。")

    relationships = set(re.findall(r"\[\s*\w*\s*:\s*([A-Za-z_][A-Za-z0-9_]*)", cypher))
    unknown_relationships = sorted(relationships - ALLOWED_RELATIONSHIPS)
    if unknown_relationships:
        raise ValueError(f"生成的 Cypher 包含未知关系类型 {', '.join(unknown_relationships)}，已拒绝执行。")


def _strip_relationship_patterns(cypher: str) -> str:
    return re.sub(r"\[[^\]]*\]", " ", cypher)
