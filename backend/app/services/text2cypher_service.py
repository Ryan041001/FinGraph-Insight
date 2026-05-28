from app.models.api import GraphPayload, Text2CypherResponse, Text2CypherSafety
from app.services.mock_data import sample_graph


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
    upper = cypher.upper()
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword in upper:
            return False, f"生成的 Cypher 包含写操作关键词 {keyword}，已拒绝执行。"
    return True, None


def answer_text2cypher(question: str) -> Text2CypherResponse:
    if is_write_intent(question):
        raise ValueError("生成的 Cypher 包含写操作意图，已拒绝执行。")

    cypher = "MATCH (c:Company)-[r]-(n) RETURN c, r, n LIMIT 50"
    passed, reason = validate_cypher(cypher)
    if not passed:
        raise ValueError(reason or "unsafe cypher")

    return Text2CypherResponse(
        cypher=cypher,
        safety=Text2CypherSafety(passed=True, rules=["read_only", "limit_checked"]),
        table={"columns": ["company", "relation", "target"], "rows": [["示例科技", "RECEIVED_FUNDING", "B轮融资事件"]]},
        graph=sample_graph(),
    )
