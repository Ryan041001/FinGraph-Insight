from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


MAX_EXTRACT_TEXT_LENGTH = 8000


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "normal"


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    label: str
    confidence: float = 1.0
    status: str = "confirmed"
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class HealthResponse(BaseModel):
    status: str
    neo4j: str
    scheduler: str


class ExtractOptions(BaseModel):
    self_refine: bool = True
    judge: bool = True
    mock: bool = False


class ExtractRequest(BaseModel):
    text: str
    options: ExtractOptions = Field(default_factory=ExtractOptions)

    @field_validator("text")
    @classmethod
    def _text_not_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text must be a non-empty string.")
        if len(value) > MAX_EXTRACT_TEXT_LENGTH:
            raise ValueError(
                f"text length must be <= {MAX_EXTRACT_TEXT_LENGTH} characters."
            )
        return value


class Text2CypherRequest(BaseModel):
    question: str


class DocumentIndexRequest(BaseModel):
    doc_id: str
    text: str
    title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Text2CypherSafety(BaseModel):
    passed: bool
    rules: list[str] = Field(default_factory=list)
    reason: str | None = None


class Text2CypherResponse(BaseModel):
    cypher: str
    safety: Text2CypherSafety
    table: dict[str, Any] = Field(default_factory=lambda: {"columns": [], "rows": []})
    graph: GraphPayload


class JobRun(BaseModel):
    job_run_id: str
    status: Literal["success", "failed", "running"]
    started_at: str
    finished_at: str | None = None
    new_documents: int = 0
    new_entities: int = 0
    new_relationships: int = 0
    failed_items: int = 0
