import re

from app.models.api import Text2CypherResponse, Text2CypherSafety
from app.services.mock_data import sample_graph


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
        table={"columns": ["company", "relation", "target"], "rows": [["示例科技", "RECEIVED_FUNDING", "B轮融资事件"]]},
        graph=sample_graph(),
    )


def _strip_comments(cypher: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", " ", cypher, flags=re.DOTALL)
    return re.sub(r"//.*?$", "", without_block_comments, flags=re.MULTILINE)


def _validate_path_depth(cypher: str) -> None:
    for match in re.finditer(r"\*\s*(\d+)?\s*\.\.\s*(\d+)", cypher):
        upper_bound = int(match.group(2))
        if upper_bound > MAX_PATH_DEPTH:
            raise ValueError(f"生成的 Cypher 路径深度超过 {MAX_PATH_DEPTH}，已拒绝执行。")
