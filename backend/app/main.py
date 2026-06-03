from pathlib import Path
from contextlib import asynccontextmanager
import hashlib
import json
import re
from collections import OrderedDict
from collections.abc import Iterable
from html import escape
from queue import Empty, Queue
from threading import RLock, Thread
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse

from app.config import settings
from app.data.financial_dataset_loader import load_financial_dataset_directory
from app.models.api import DocumentIndexRequest, ExtractRequest, GraphPayload, HealthResponse, Text2CypherRequest, Text2CypherSafety, UnifiedQaRequest
from app.neo4j.connection import check_neo4j_health, close_neo4j_driver, get_neo4j_driver
from app.neo4j.reader import execute_readonly_cypher
from app.services.extraction_service import (
    extract_with_llm,
    judge_extraction_with_llm,
)
from app.services.format_prompt import HTML_CHAT_FORMAT_INSTRUCTIONS
from app.services.graph_rag_service import answer_with_llm_graph_context, answer_with_hybrid_context
from app.services.graph_query_service import company_profile, paths, subgraph
from app.services.graph_runtime import import_extraction_payload_runtime, import_graph_runtime
from app.services.graph_store import graph_store
from app.services.hybrid_rag_service import answer_with_hybrid_rag
from app.services.market_service import MarketDataError, build_kline_response
from app.services.metrics_service import default_gold_standard_path, evaluate_gold_standard
from app.services.scheduler_service import (
    get_job_run,
    list_job_runs,
    run_akshare_update,
    scheduler_status,
    shutdown_scheduler,
    start_akshare_update_async,
    start_scheduler,
)
from app.services.self_refine_service import extract_with_self_refine
from app.services.stock_analysis_service import (
    build_stock_analysis,
    summarize_stock_analysis_with_llm,
)
from app.services.llm_service import HttpLLMGateway, LLMTask
from app.services.text2cypher_service import (
    answer_text2cypher,
    generate_cypher_with_llm,
    is_write_intent,
)
from app.services.vector_store import vector_store
from app.logging_config import configure_logging, get_logger


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("backend starting: graph_backend=%s scheduler_enabled=%s", settings.graph_backend, settings.scheduler_enabled)
    start_scheduler()
    _start_startup_preload()
    try:
        yield
    finally:
        logger.info("backend shutting down")
        shutdown_scheduler()
        close_neo4j_driver()


_PRELOAD_STATE: dict[str, object] = {
    "dataset_status": "skipped",
    "dataset_started_at": None,
    "dataset_finished_at": None,
    "dataset_nodes": 0,
    "dataset_relationships": 0,
    "akshare_status": "skipped",
    "akshare_job_run_id": None,
    "error": None,
}
_PRELOAD_STATE_LOCK = RLock()


def _update_preload_state(updates: dict) -> None:
    with _PRELOAD_STATE_LOCK:
        _PRELOAD_STATE.update(updates)


def _snapshot_preload_state() -> dict:
    with _PRELOAD_STATE_LOCK:
        return dict(_PRELOAD_STATE)


def _start_startup_preload() -> None:
    if not settings.startup_preload_dataset and not settings.startup_refresh_akshare:
        return

    def worker() -> None:
        from datetime import datetime

        if settings.startup_preload_dataset:
            _update_preload_state({
                "dataset_status": "running",
                "dataset_started_at": datetime.now().isoformat(timespec="seconds"),
                "error": None,
            })
            try:
                graph = _load_dataset_graph("financial_datasets")
                stats = import_graph_runtime(graph)
                _update_preload_state({
                    "dataset_status": "ready",
                    "dataset_finished_at": datetime.now().isoformat(timespec="seconds"),
                    "dataset_nodes": getattr(stats, "nodes_created", 0) + getattr(stats, "nodes_matched", 0),
                    "dataset_relationships": getattr(stats, "relationships_created", 0) + getattr(stats, "relationships_skipped", 0),
                })
            except Exception as exc:
                logger.exception("startup dataset preload failed")
                _update_preload_state({
                    "dataset_status": "failed",
                    "dataset_finished_at": datetime.now().isoformat(timespec="seconds"),
                    "error": str(exc)[:240],
                })

        if settings.startup_refresh_akshare:
            try:
                job = start_akshare_update_async()
                _update_preload_state({
                    "akshare_status": "running",
                    "akshare_job_run_id": job.job_run_id,
                })
            except Exception as exc:
                _update_preload_state({
                    "akshare_status": "failed",
                    "error": str(exc)[:240],
                })

    Thread(target=worker, daemon=True).start()


app = FastAPI(title="Financial KG API", version="0.1.0", lifespan=lifespan)


def _cors_allow_origins() -> list[str]:
    raw = settings.cors_allow_origins.strip()
    if not raw or raw == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]


_cors_origins = _cors_allow_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_stock_analysis_cache: "OrderedDict[str, dict]" = OrderedDict()
_stock_analysis_cache_lock = RLock()
SSE_HEARTBEAT_SECONDS = 8.0


def _record_stock_analysis(stock_code: str, payload: dict) -> None:
    max_size = max(1, settings.stock_analysis_cache_max_size)
    with _stock_analysis_cache_lock:
        _stock_analysis_cache[stock_code] = payload
        _stock_analysis_cache.move_to_end(stock_code)
        while len(_stock_analysis_cache) > max_size:
            _stock_analysis_cache.popitem(last=False)


def _get_cached_stock_analysis(stock_code: str) -> dict | None:
    with _stock_analysis_cache_lock:
        payload = _stock_analysis_cache.get(stock_code)
        if payload is not None:
            _stock_analysis_cache.move_to_end(stock_code)
        return payload


def _raise_llm_error(exc: Exception) -> None:
    logger.warning("LLM call failed: %s", exc, exc_info=True)
    raise HTTPException(
        status_code=502,
        detail={
            "error": "llm_error",
            "message": _sanitize_llm_error_message(str(exc)),
        },
    ) from exc


_LLM_ERROR_URL_PATTERN = re.compile(r"https?://\S+", flags=re.IGNORECASE)


def _sanitize_llm_error_message(message: str) -> str:
    if not message:
        return "上游模型服务暂时不可用，请稍后重试。"
    sanitized = _LLM_ERROR_URL_PATTERN.sub("<llm endpoint>", message)
    sanitized = sanitized.replace("\n", " ").strip()
    if len(sanitized) > 240:
        sanitized = sanitized[:237] + "..."
    return sanitized


@app.exception_handler(RequestValidationError)
async def _request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    field_errors = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()) if part not in {"body"})
        field_errors.append(
            {
                "field": location or "(root)",
                "message": error.get("msg", "invalid value"),
                "type": error.get("type", "value_error"),
            }
        )
    return JSONResponse(
        status_code=422,
        content={
            "error": "invalid_input",
            "message": "请求参数校验失败。",
            "fields": field_errors,
        },
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", neo4j=_graph_health_status(), scheduler=scheduler_status())


@app.get("/preload")
def get_preload_state() -> dict:
    return _snapshot_preload_state()


def _graph_health_status() -> str:
    if settings.graph_backend.lower() != "neo4j":
        return graph_store.health_status()

    try:
        driver = get_neo4j_driver()
    except Exception:
        return "unavailable"
    return check_neo4j_health(driver)


@app.post("/datasets/import")
def import_dataset(payload: dict | None = None) -> dict:
    dataset = (payload or {}).get("dataset", "financial_datasets")
    if dataset != "financial_datasets":
        raise HTTPException(status_code=400, detail={"error": "invalid_input", "message": f"unsupported dataset: {dataset}"})

    graph = _load_dataset_graph(dataset)
    stats = import_graph_runtime(graph)
    return {
        "import_run_id": "import_financial_datasets",
        "nodes_created": stats.nodes_created,
        "relationships_created": stats.relationships_created,
        "nodes_skipped": stats.nodes_matched,
        "relationships_skipped": stats.relationships_skipped,
        "status": "success",
    }


_DATASET_CACHE: dict[str, tuple[float, object]] = {}
_DATASET_CACHE_LOCK = RLock()


def _dataset_signature(dataset_path: Path) -> float:
    latest = 0.0
    for entry in dataset_path.rglob("*"):
        if entry.is_file():
            try:
                latest = max(latest, entry.stat().st_mtime)
            except OSError:
                continue
    return latest


def _load_dataset_graph_cached(dataset_path: Path):
    cache_key = str(dataset_path.resolve())
    signature = _dataset_signature(dataset_path)
    with _DATASET_CACHE_LOCK:
        cached = _DATASET_CACHE.get(cache_key)
        if cached is not None and cached[0] == signature:
            return cached[1]
    graph = load_financial_dataset_directory(dataset_path)
    with _DATASET_CACHE_LOCK:
        _DATASET_CACHE[cache_key] = (signature, graph)
    return graph


def _load_dataset_graph(dataset: str):
    if dataset == "financial_datasets":
        for dataset_path in _dataset_candidate_paths():
            if not dataset_path.exists():
                continue
            graph = _load_dataset_graph_cached(dataset_path)
            if graph.nodes:
                return graph
    raise HTTPException(
        status_code=404,
        detail={"error": "dataset_not_found", "message": "financial dataset files were not found or produced no nodes"},
    )


def _dataset_candidate_paths(app_file: str | Path | None = None) -> list[Path]:
    app_path = Path(app_file or __file__).resolve()
    roots: list[Path] = []
    for parent_index in (2, 1):
        try:
            root = app_path.parents[parent_index]
        except IndexError:
            continue
        if root not in roots:
            roots.append(root)

    paths: list[Path] = []
    for root in roots:
        paths.extend([
            root / "data" / "raw" / "FinancialDatasets",
            root / "data" / "processed",
        ])
    return paths


@app.post("/extract")
def extract(request: ExtractRequest) -> dict:
    if request.options.mock:
        raise HTTPException(
            status_code=400,
            detail={"error": "mock_disabled", "message": "mock extraction is disabled for business runtime"},
        )

    try:
        gateway = HttpLLMGateway()
        if request.options.self_refine:
            payload = extract_with_self_refine(request.text, gateway)
        else:
            payload = extract_with_llm(request.text, gateway)
        if request.options.judge:
            payload = judge_extraction_with_llm(payload, gateway)
        return payload
    except Exception as exc:
        _raise_llm_error(exc)


@app.post("/graph/import")
def import_graph(payload: dict) -> dict:
    stats = import_extraction_payload_runtime(payload)
    return {
        "nodes_created": stats.nodes_created,
        "nodes_matched": stats.nodes_matched,
        "relationships_created": stats.relationships_created,
        "relationships_skipped": stats.relationships_skipped,
        "status": "success",
    }


@app.get("/graph/company/{name}")
def get_company_profile(name: str, depth: int = Query(2, ge=1, le=3), include_pending: bool = False) -> dict:
    payload = company_profile(name, depth=depth)
    graph = payload.get("graph") or {}
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    payload["found"] = bool(nodes or edges)
    return payload


@app.get("/graph/companies")
def search_companies(
    q: str = Query("", description="模糊搜索关键字，留空返回前 N 条"),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    matches = graph_store.search_companies(q, limit=limit)
    return {
        "query": q,
        "total": len(matches),
        "companies": [
            {"id": node.id, "name": node.label, "industry": node.properties.get("industry", "未知")}
            for node in matches
        ],
    }


@app.get("/graph/common-investors")
def common_investors(
    companies: str = Query(..., description="多个公司名用逗号分隔，至少 2 个"),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    company_names = [name.strip() for name in companies.split(",") if name.strip()]
    if len(company_names) < 2:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_input", "message": "companies 至少需要传入 2 个公司名（逗号分隔）。"},
        )
    matches = graph_store.common_investors(company_names, limit=limit)
    return {
        "companies": company_names,
        "total": len(matches),
        "investors": matches,
    }


@app.get("/graph/subgraph")
def get_subgraph(
    entity: str,
    depth: int = Query(2, ge=1, le=3),
    limit: int = Query(80, ge=1, le=200),
) -> dict:
    return subgraph(entity, depth=depth, limit=limit)


@app.get("/graph/path")
def get_path(
    source: str,
    target: str,
    max_depth: int = Query(4, ge=1, le=4),
) -> dict:
    return paths(source, target, max_depth=max_depth)


@app.post("/qa/graph-rag")
def graph_rag(payload: dict) -> dict:
    company_name = extract_company_name_from_question(payload.get("question"))
    graph = graph_store.subgraph(company_name)
    try:
        response = answer_with_llm_graph_context(str(payload.get("question", "")), graph, HttpLLMGateway())
        hybrid = answer_with_hybrid_context(str(payload.get("question", "")), graph)
        response["document_context"] = hybrid["document_context"]
        response["retrieval"] = {
            **hybrid["retrieval"],
            "llm_used": True,
            "answer_source": "llm",
        }
        response["citations"] = [*response["citations"], *hybrid["citations"][len(response["citations"]) :]]
        return response
    except Exception as exc:
        _raise_llm_error(exc)


@app.post("/qa/graph-rag/stream")
def graph_rag_stream(payload: dict) -> StreamingResponse:
    question = str(payload.get("question", ""))
    company_name = extract_company_name_from_question(question)
    graph = graph_store.subgraph(company_name)
    fallback = answer_with_hybrid_context(question, graph)
    messages = [
        {
            "role": "system",
            "content": (
                "你是金融知识图谱问答助手。只能基于用户提供的 supporting_graph 和 document_context 回答。"
                "直接输出适合前端逐字展示的中文回答，不要输出 JSON、Cypher 或 Markdown 表格。"
                f"\n{HTML_CHAT_FORMAT_INSTRUCTIONS}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": question,
                    "supporting_graph": graph.model_dump(),
                    "document_context": fallback["document_context"],
                },
                ensure_ascii=False,
            ),
        },
    ]
    token_stream = HttpLLMGateway().stream_complete(
        task=LLMTask.GRAPH_RAG_STREAM,
        messages=messages,
        temperature=0,
        max_tokens=1024,
    )
    return _sse_stream(
        token_stream,
        metadata={
            "supporting_graph": graph.model_dump(),
            "citations": fallback["citations"],
            "tool_calls": _graph_tool_calls(company_name),
            "retrieval": {
                **fallback["retrieval"],
                "llm_used": True,
                "answer_source": "llm_stream",
            },
        },
    )


@app.post("/qa/hybrid-rag")
def hybrid_rag(payload: dict) -> dict:
    question = str(payload.get("question", ""))
    entity = payload.get("entity")
    try:
        return answer_with_hybrid_rag(question, entity=entity, gateway=HttpLLMGateway())
    except Exception as exc:
        _raise_llm_error(exc)


@app.post("/qa/hybrid-rag/stream")
def hybrid_rag_stream(payload: dict) -> StreamingResponse:
    question = str(payload.get("question", ""))
    entity = payload.get("entity")
    target_entity = str(entity) if entity else extract_company_name_from_question(question)
    graph = graph_store.subgraph(target_entity)
    fallback = answer_with_hybrid_context(question, graph)
    messages = [
        {
            "role": "system",
            "content": (
                "你是金融知识图谱问答助手。只能基于 supporting_graph 和 document_context 回答，"
                "直接输出适合前端逐字展示的中文回答，不要输出 JSON。"
                f"\n{HTML_CHAT_FORMAT_INSTRUCTIONS}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": question,
                    "supporting_graph": graph.model_dump(),
                    "document_context": fallback["document_context"],
                },
                ensure_ascii=False,
            ),
        },
    ]
    token_stream = HttpLLMGateway().stream_complete(
        task=LLMTask.GRAPH_RAG_STREAM,
        messages=messages,
        temperature=0,
        max_tokens=1024,
    )
    return _sse_stream(
        token_stream,
        metadata={
            "supporting_graph": graph.model_dump(),
            "document_context": fallback["document_context"],
            "citations": fallback["citations"],
            "tool_calls": _graph_tool_calls(target_entity),
            "retrieval": {
                **fallback["retrieval"],
                "llm_used": True,
                "answer_source": "llm_stream",
            },
        },
    )


@app.post("/rag/documents")
def index_rag_document(request: DocumentIndexRequest) -> dict:
    chunks_indexed = vector_store.add_document(
        doc_id=request.doc_id,
        title=request.title,
        text=request.text,
        metadata=request.metadata,
    )
    return {"doc_id": request.doc_id, "chunks_indexed": chunks_indexed, "status": "success"}


def extract_company_name_from_question(question: object) -> str:
    if not isinstance(question, str):
        return "该企业"

    normalized_question = question.strip()
    if not normalized_question:
        return "该企业"

    for separator in ("：", ":"):
        if separator in normalized_question:
            candidate = normalized_question.split(separator, 1)[0].strip()
            if candidate:
                return candidate

    try:
        candidates = graph_store.search_companies(normalized_question, limit=1)
    except Exception:
        candidates = []
    if candidates:
        return candidates[0].label

    for company in _iter_company_labels():
        if company and company in normalized_question:
            return company

    return "该企业"


def _iter_company_labels():
    try:
        all_graph = graph_store.all_graph()
    except Exception:
        return []
    return [node.label for node in all_graph.nodes if node.type == "Company" and node.label]


@app.post("/qa/unified")
def unified_qa(request: UnifiedQaRequest) -> dict:
    context = _build_unified_qa_context(request, use_llm_answer=True)
    rag_response = context["rag_response"]
    answer = str(rag_response.get("answer") or "暂未获得有效回答，请稍后重试。")
    answer = _ensure_inline_html_answer(answer, context["table"])
    supporting_graph = _answer_supporting_graph(rag_response, context["graph"])
    return {
        "answer": answer,
        "cypher": context["cypher"],
        "safety": context["safety"],
        "table": context["table"],
        "graph": supporting_graph,
        "supporting_graph": supporting_graph,
        "citations": rag_response.get("citations", []),
        "document_context": rag_response.get("document_context", []),
        "retrieval": rag_response.get("retrieval", {}),
        "status": context["status"],
        "messages": context["messages"],
    }


_EVIDENCE_HTML_PATTERN = re.compile(r"<table\b|qa-evidence-table|qa-insight-card", re.IGNORECASE)


def _ensure_inline_html_answer(answer: str, table: dict[str, object]) -> str:
    if _EVIDENCE_HTML_PATTERN.search(answer):
        return answer
    evidence_table = _build_inline_evidence_table(table)
    if not evidence_table:
        return answer
    return f"{answer.rstrip()}\n\n{evidence_table}"


def _build_inline_evidence_table(table: dict[str, object]) -> str:
    raw_columns = table.get("columns")
    raw_rows = table.get("rows")
    if not isinstance(raw_columns, list) or not isinstance(raw_rows, list) or not raw_columns or not raw_rows:
        return ""

    columns = [str(column) for column in raw_columns[:6]]
    rows = [row for row in raw_rows[:8] if isinstance(row, list)]
    if not rows:
        return ""

    card_style = (
        "border: 1px solid #bae6fd; border-radius: 8px; background: #f0f9ff; "
        "padding: 12px; margin-top: 12px;"
    )
    title_style = "display: block; color: #075985; margin-bottom: 8px;"
    table_style = "width: 100%; border-collapse: collapse; background: #ffffff;"
    th_style = (
        "border: 1px solid #bae6fd; background: #e0f2fe; color: #0f172a; "
        "padding: 8px; text-align: left;"
    )
    td_style = "border: 1px solid #bae6fd; color: #334155; padding: 8px; text-align: left;"

    header = "".join(f'<th style="{th_style}">{escape(column)}</th>' for column in columns)
    body_rows = []
    for row in rows:
        cells = []
        for index in range(len(columns)):
            value = row[index] if index < len(row) else ""
            cells.append(f'<td style="{td_style}">{escape(_html_table_cell(value))}</td>')
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    return (
        f'<div style="{card_style}">'
        f'<strong style="{title_style}">审计证据摘要</strong>'
        f'<table style="{table_style}">'
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
        "</div>"
    )


def _html_table_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


@app.post("/qa/unified/stream")
def unified_qa_stream(request: UnifiedQaRequest) -> StreamingResponse:
    context = _build_unified_qa_context(request, use_llm_answer=False)
    rag_response = context["rag_response"]
    supporting_graph = _answer_supporting_graph(rag_response, context["graph"])
    metadata = {
        "cypher": context["cypher"],
        "safety": context["safety"],
        "table": context["table"],
        "graph": supporting_graph,
        "supporting_graph": supporting_graph,
        "citations": rag_response.get("citations", []),
        "document_context": rag_response.get("document_context", []),
        "retrieval": {
            **(rag_response.get("retrieval") if isinstance(rag_response.get("retrieval"), dict) else {}),
            "llm_used": True,
            "answer_source": "llm_stream",
        },
        "status": context["status"],
        "messages": context["messages"],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "你是金融知识图谱问答助手。只能基于 supporting_graph 和 document_context 回答，"
                "直接输出适合前端逐字展示的中文回答，不要输出 JSON。"
                "可以使用 Markdown 和受控局部 HTML。"
                f"\n{HTML_CHAT_FORMAT_INSTRUCTIONS}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": context["contextual_question"],
                    "supporting_graph": supporting_graph,
                    "document_context": metadata["document_context"],
                },
                ensure_ascii=False,
            ),
        },
    ]
    token_stream = HttpLLMGateway().stream_complete(
        task=LLMTask.GRAPH_RAG_STREAM,
        messages=messages,
        temperature=0,
        max_tokens=1024,
    )
    return _sse_stream(token_stream, metadata=metadata)


def _answer_supporting_graph(rag_response: dict[str, object], fallback_graph: GraphPayload) -> dict[str, object]:
    supporting_graph = rag_response.get("supporting_graph")
    if isinstance(supporting_graph, dict):
        nodes = supporting_graph.get("nodes")
        edges = supporting_graph.get("edges")
        if isinstance(nodes, list) and isinstance(edges, list):
            return supporting_graph
    return fallback_graph.model_dump()


def _build_unified_qa_context(request: UnifiedQaRequest, *, use_llm_answer: bool) -> dict[str, Any]:
    question = request.question.strip()
    target_entity = (request.entity or request.company_name or extract_company_name_from_question(question)).strip() or "该企业"
    contextual_question = question if target_entity in question else f"{target_entity}：{question}"
    graph = _runtime_subgraph_payload(target_entity)
    status: dict[str, str] = {"text2cypher": "pending", "rag": "pending"}
    messages: list[str] = []
    cypher = ""
    safety = Text2CypherSafety(passed=False, rules=[], reason="not_run").model_dump()
    table: dict[str, object] = {"columns": [], "rows": []}
    query_graph: dict[str, object] = {"nodes": [], "edges": []}

    if is_write_intent(contextual_question):
        status["text2cypher"] = "skipped"
        safety = Text2CypherSafety(passed=False, rules=[], reason="写操作意图已跳过图查询").model_dump()
        messages.append("已跳过不适合执行的图查询。")
    else:
        try:
            cypher, rules = generate_cypher_with_llm(contextual_question, HttpLLMGateway())
            safety = Text2CypherSafety(passed=True, rules=rules).model_dump()
            if settings.graph_backend.lower() == "neo4j":
                cypher_result = execute_readonly_cypher(get_neo4j_driver(), cypher)
                table = cypher_result.get("table", table)
                query_graph = cypher_result.get("graph", query_graph)
                query_graph = _enrich_node_only_audit_graph(query_graph, graph)
                status["text2cypher"] = "ok"
                if _graph_edge_count(query_graph) > 0:
                    messages.append("已在 Neo4j 执行查询并生成可视化。")
            else:
                memory_result = _build_memory_audit_query_result(target_entity, graph)
                table = memory_result["table"]
                query_graph = memory_result["graph"]
                if memory_result["has_graph"]:
                    status["text2cypher"] = "ok"
                    messages.append("已在本地图谱执行查询并生成可视化。")
                else:
                    status["text2cypher"] = "generated"
                    messages.append("图查询语句已生成，本地图谱暂未查询到可视化结果。")
        except Exception:
            status["text2cypher"] = "failed"
            messages.append("图查询暂未生成，已继续基于可用上下文回答。")

    rag_response: dict[str, object] = {}
    try:
        rag_response = answer_with_hybrid_rag(
            contextual_question,
            entity=target_entity,
            gateway=HttpLLMGateway() if use_llm_answer else None,
        )
        status["rag"] = "ok"
    except Exception:
        status["rag"] = "fallback"
        rag_response = answer_with_hybrid_context(contextual_question, graph)
        messages.append("AI回答暂未调用成功，已基于现有证据生成基础回答。")

    if _unified_response_needs_public_evidence(rag_response, graph):
        augmented_response = _augment_unified_response_with_public_evidence(
            rag_response=rag_response,
            target_entity=target_entity,
            graph=graph,
        )
        if augmented_response is not rag_response:
            rag_response = augmented_response
            refreshed_graph = _runtime_subgraph_payload(target_entity)
            if refreshed_graph.nodes or refreshed_graph.edges:
                graph = refreshed_graph
                if _graph_edge_count(query_graph) == 0:
                    memory_result = _build_memory_audit_query_result(target_entity, graph)
                    table = memory_result["table"]
                    query_graph = memory_result["graph"]
                    if memory_result["has_graph"]:
                        status["text2cypher"] = "ok"
            messages.append("已补充企业证据线索并继续回答。")

    return {
        "question": question,
        "target_entity": target_entity,
        "contextual_question": contextual_question,
        "graph": graph,
        "rag_response": rag_response,
        "cypher": cypher,
        "safety": safety,
        "table": table,
        "query_graph": query_graph,
        "status": status,
        "messages": messages,
    }


def _runtime_subgraph_payload(target_entity: str) -> GraphPayload:
    if settings.graph_backend.lower() == "neo4j":
        try:
            runtime_graph = GraphPayload.model_validate(subgraph(target_entity))
            if runtime_graph.nodes or runtime_graph.edges:
                return runtime_graph
        except Exception:
            pass
    return graph_store.subgraph(target_entity)


def _enrich_node_only_audit_graph(query_graph: dict[str, object], entity_graph: GraphPayload) -> dict[str, object]:
    if _graph_edge_count(query_graph) > 0:
        return query_graph
    if entity_graph.edges:
        return entity_graph.model_dump()
    return query_graph


def _graph_edge_count(graph: dict[str, object]) -> int:
    edges = graph.get("edges")
    return len(edges) if isinstance(edges, list) else 0


def _build_memory_audit_query_result(target_entity: str, graph: GraphPayload) -> dict[str, Any]:
    query_graph = graph
    if not query_graph.nodes and target_entity:
        query_graph = graph_store.subgraph(target_entity)

    rows = [
        [node.label, node.type, node.risk_level]
        for node in query_graph.nodes[:50]
    ]
    return {
        "table": {
            "columns": ["节点", "类型", "风险等级"],
            "rows": rows,
        },
        "graph": query_graph.model_dump(),
        "has_graph": bool(query_graph.nodes or query_graph.edges),
    }


def _unified_response_needs_public_evidence(rag_response: dict[str, object], graph: GraphPayload) -> bool:
    supporting_graph = rag_response.get("supporting_graph")
    if not isinstance(supporting_graph, dict):
        supporting_graph = graph.model_dump()

    nodes = supporting_graph.get("nodes") if isinstance(supporting_graph, dict) else []
    edges = supporting_graph.get("edges") if isinstance(supporting_graph, dict) else []
    document_context = rag_response.get("document_context")
    return not nodes and not edges and not document_context


def _augment_unified_response_with_public_evidence(
    *,
    rag_response: dict[str, object],
    target_entity: str,
    graph: GraphPayload,
) -> dict[str, object]:
    try:
        analysis = build_stock_analysis(
            {
                "stock_code": "",
                "company_name": target_entity,
                "refresh_news": True,
                "enrich_fundamentals": False,
            },
            news_gateway=HttpLLMGateway(),
        )
        _sanitize_stock_analysis_missing_data(analysis)
    except Exception:
        return rag_response

    raw_events = analysis.get("news_events")
    events = [event for event in raw_events if isinstance(event, dict)] if isinstance(raw_events, list) else []
    document_context = _news_events_to_document_context(target_entity, events)
    if not document_context:
        return rag_response

    citations = _news_context_to_citations(document_context)
    retrieval = rag_response.get("retrieval")
    if not isinstance(retrieval, dict):
        retrieval = {}
    refreshed_graph = _runtime_subgraph_payload(target_entity)
    supporting_graph = refreshed_graph.model_dump() if (refreshed_graph.nodes or refreshed_graph.edges) else graph.model_dump()

    return {
        **rag_response,
        "answer": _synthesize_unified_answer_from_evidence(
            target_entity=target_entity,
            document_context=document_context,
            analysis=analysis,
        ),
        "supporting_graph": supporting_graph,
        "document_context": document_context,
        "citations": [*(rag_response.get("citations") if isinstance(rag_response.get("citations"), list) else []), *citations],
        "retrieval": {
            **retrieval,
            "mode": "hybrid",
            "graph_nodes": len(supporting_graph.get("nodes", [])),
            "graph_edges": len(supporting_graph.get("edges", [])),
            "document_chunks": document_context and len(document_context) or 0,
            "realtime_events": len(document_context),
            "answer_source": "evidence_fallback",
        },
    }


def _news_events_to_document_context(company_name: str, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for index, event in enumerate(events[:5], start=1):
        title = str(event.get("title") or f"{company_name}证据线索{index}").strip()
        evidence = str(event.get("evidence") or title).strip()
        if not title and not evidence:
            continue

        date = str(event.get("date") or "未知").strip() or "未知"
        source_url = str(event.get("source_url") or "").strip()
        event_type = str(event.get("event_type") or "public_info").strip() or "public_info"
        text = _join_evidence_parts([title, evidence, f"日期：{date}" if date != "未知" else ""])
        digest = hashlib.sha1(f"{company_name}|{title}|{evidence}|{index}".encode("utf-8")).hexdigest()[:12]
        doc_id = f"evidence_{digest}"
        chunks.append(
            {
                "chunk_id": f"{doc_id}_0001",
                "doc_id": doc_id,
                "title": title,
                "text": text,
                "metadata": {
                    "company_name": company_name,
                    "event_type": event_type,
                    "date": date,
                    "source": "证据线索",
                    "source_url": source_url,
                },
                "score": round(max(0.2, 1.0 - (index - 1) * 0.08), 6),
            }
        )
    return chunks


def _news_context_to_citations(document_context: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for chunk in document_context:
        citations.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "doc_id": chunk.get("doc_id"),
                "source": "证据线索",
                "source_text": chunk.get("text", ""),
                "score": chunk.get("score", 0),
            }
        )
    return citations


def _synthesize_unified_answer_from_evidence(
    *,
    target_entity: str,
    document_context: list[dict[str, Any]],
    analysis: dict[str, Any],
) -> str:
    analysis_block = analysis.get("analysis") if isinstance(analysis.get("analysis"), dict) else {}
    summary = str(analysis_block.get("summary") or "").strip()
    lines = [f"{target_entity}的可用证据线索如下："]
    if summary:
        lines.append(summary)
    for chunk in document_context[:3]:
        title = str(chunk.get("title") or "证据线索").strip()
        text = str(chunk.get("text") or "").strip()
        metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
        date = str(metadata.get("date") or "").strip()
        date_text = f"（{date}）" if date and date != "未知" else ""
        lines.append(f"- {title}{date_text}：{text}")
    lines.append("以上内容仅用于课程项目演示和研究辅助，不构成投资建议。")
    return "\n".join(lines)


def _join_evidence_parts(parts: list[str]) -> str:
    seen: list[str] = []
    for part in parts:
        text = part.strip()
        if text and text not in seen:
            seen.append(text)
    return "；".join(seen)


@app.post("/qa/text2cypher")
def text2cypher(request: Text2CypherRequest):
    try:
        if is_write_intent(request.question):
            raise ValueError("生成的 Cypher 包含写操作意图，已拒绝执行。")

        cypher, rules = generate_cypher_with_llm(request.question, HttpLLMGateway())
        safety = Text2CypherSafety(passed=True, rules=rules).model_dump()
        if settings.graph_backend.lower() == "neo4j":
            result = execute_readonly_cypher(get_neo4j_driver(), cypher)
            return {"cypher": cypher, "safety": safety, **result}
        return {
            "cypher": cypher,
            "safety": safety,
            "table": {"columns": [], "rows": []},
            "graph": {"nodes": [], "edges": []},
            "note": "当前未启用 Neo4j 后端，仅返回生成的 Cypher 文本未执行；请将 GRAPH_BACKEND 切换到 neo4j 后查询。",
        }
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": "unsafe_cypher",
                "message": str(exc),
                "cypher": "",
            },
        )
    except Exception as exc:
        _raise_llm_error(exc)


@app.get("/jobs")
def list_jobs() -> dict:
    return {"jobs": [job.model_dump() for job in list_job_runs()]}


@app.post("/jobs/akshare/run")
def run_akshare_job() -> dict:
    return start_akshare_update_async().model_dump()


@app.get("/jobs/{job_run_id}")
def get_job(job_run_id: str) -> dict:
    job = get_job_run(job_run_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "scheduler_error", "message": "job run not found"})
    return job.model_dump()


@app.get("/metrics/extraction")
def extraction_metrics() -> dict:
    try:
        return evaluate_gold_standard(default_gold_standard_path())
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "metrics_unavailable", "message": str(exc)},
        ) from exc


@app.post("/metrics/evaluate")
def evaluate_metrics() -> dict:
    return extraction_metrics()


@app.post("/analysis/stock")
def stock_analysis(payload: dict) -> dict:
    use_llm = bool(payload.get("use_llm", False))
    if payload.get("refresh_news"):
        try:
            result = build_stock_analysis(payload, news_gateway=HttpLLMGateway())
        except Exception:
            result = build_stock_analysis({**payload, "refresh_news": False})
            missing_data = result["analysis"].setdefault("missing_data", [])
            missing_data.append("部分信息暂未获取，已基于现有证据生成。")
    else:
        result = build_stock_analysis(payload)

    if use_llm:
        try:
            result = summarize_stock_analysis_with_llm(result, HttpLLMGateway())
        except Exception:
            missing_data = result["analysis"].setdefault("missing_data", [])
            missing_data.append("部分信息暂未获取，已基于现有证据生成。")

    _sanitize_stock_analysis_missing_data(result)
    stock_code = str(result.get("target", {}).get("stock_code") or payload.get("stock_code") or "")
    if stock_code:
        _record_stock_analysis(stock_code, result)
    return result


def _sanitize_stock_analysis_missing_data(result: dict) -> None:
    analysis = result.get("analysis")
    if not isinstance(analysis, dict):
        return
    raw_missing = analysis.get("missing_data")
    if not isinstance(raw_missing, list):
        analysis["missing_data"] = []
        return
    if not raw_missing:
        return

    product_messages: list[str] = []
    for item in raw_missing:
        text = str(item)
        if _is_technical_missing_data(text):
            continue
        if text and text not in product_messages:
            product_messages.append(text)
    if not product_messages:
        product_messages = ["部分信息暂未获取，已基于现有证据生成。"]
    analysis["missing_data"] = product_messages[:3]


def _is_technical_missing_data(text: str) -> bool:
    technical_markers = (
        "yfinance",
        "LLM",
        "missing choices",
        "Server error",
        "Service Unavailable",
        "503",
        "OPENAI",
        "API_KEY",
        "股票代码无法解析",
        "基本面字段补充失败",
        "新闻补充暂不可用",
        "模型研判暂不可用",
    )
    return any(marker in text for marker in technical_markers)


@app.get("/analysis/stock/{stock_code}/latest")
def latest_stock_analysis(stock_code: str) -> dict:
    cached = _get_cached_stock_analysis(stock_code)
    if cached:
        return cached
    result = build_stock_analysis({"stock_code": stock_code, "company_name": stock_code})
    _sanitize_stock_analysis_missing_data(result)
    return result


@app.post("/analysis/stock/stream")
def stock_analysis_stream(payload: dict) -> StreamingResponse:
    def events():
        queue: Queue[tuple[str, dict[str, Any] | None]] = Queue()

        def emit(event: str, data: dict[str, Any]) -> None:
            queue.put((event, data))

        def build_analysis() -> None:
            try:
                stock_code = str(payload.get("stock_code") or "")
                company_name = str(payload.get("company_name") or stock_code or "未知上市公司")
                target = {"stock_code": stock_code, "company_name": company_name}
                emit("metadata", {"target": target, "tool_calls": _stock_tool_calls(target)})
                emit("status", {"stage": "evidence", "message": "正在补充证据线索。"})

                result = _build_stock_analysis_for_stream(payload, emit)
                emit("subgraph", {"subgraph": result.get("subgraph", {"nodes": [], "edges": []})})

                if bool(payload.get("use_llm", False)):
                    emit("status", {"stage": "analysis", "message": "正在生成 AI 研判。"})
                    try:
                        result = summarize_stock_analysis_with_llm(result, HttpLLMGateway())
                    except Exception:
                        missing_data = result["analysis"].setdefault("missing_data", [])
                        missing_data.append("部分信息暂未获取，已基于现有证据生成。")

                _sanitize_stock_analysis_missing_data(result)
                stock_code = str(result.get("target", {}).get("stock_code") or payload.get("stock_code") or "")
                if stock_code:
                    _record_stock_analysis(stock_code, result)
                emit("analysis", {"analysis": result.get("analysis", {})})
                emit("done", result)
            except Exception as exc:
                logger.warning("stock analysis SSE failed: %s", exc, exc_info=True)
                emit("error", {"error": "analysis_error", "message": "证据线索研判暂不可用，请稍后重试。"})
            finally:
                queue.put(("close", None))

        Thread(target=build_analysis, daemon=True).start()

        while True:
            try:
                event_type, data = queue.get(timeout=SSE_HEARTBEAT_SECONDS)
            except Empty:
                yield _sse_event("ping", {"status": "waiting"})
                continue

            if event_type == "close":
                break
            yield _sse_event(event_type, data or {})

    return StreamingResponse(events(), media_type="text/event-stream")


def _build_stock_analysis_for_stream(payload: dict, emit) -> dict:
    if payload.get("refresh_news"):
        try:
            return build_stock_analysis(
                payload,
                news_gateway=HttpLLMGateway(),
                on_news_event=lambda event: emit("news_event", {"event": event}),
            )
        except Exception:
            result = build_stock_analysis({**payload, "refresh_news": False})
            missing_data = result["analysis"].setdefault("missing_data", [])
            missing_data.append("部分信息暂未获取，已基于现有证据生成。")
            return result
    return build_stock_analysis(payload)


@app.get("/market/kline/{stock_code}")
def get_market_kline(
    stock_code: str,
    market: Literal["A", "HK"] = "A",
    period: Literal["daily", "weekly", "monthly"] = "daily",
    start_date: str | None = None,
    end_date: str | None = None,
    adjust: Literal["qfq", "hfq", ""] = "qfq",
    company_name: str | None = Query(None, description="可选公司名，用于从图谱拼接事件标注"),
) -> dict:
    try:
        payload = build_kline_response(
            stock_code=stock_code,
            market=market,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
    except MarketDataError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "market_data_error", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "market_data_error", "message": str(exc)},
        ) from exc

    target_name = (company_name or payload.get("company_name") or "").strip()
    if target_name and target_name != stock_code:
        payload["events"] = _kline_events_for_company(target_name)
    return payload


def _kline_events_for_company(company_name: str) -> list[dict]:
    try:
        events = graph_store.events_for_company(company_name, limit=30)
    except Exception:
        return []
    annotations: list[dict] = []
    for event in events:
        props = event.properties or {}
        date = props.get("date") or ""
        if not date:
            continue
        annotations.append(
            {
                "date": date,
                "label": event.label,
                "event_type": props.get("event_type", "funding"),
                "round": props.get("round", ""),
                "amount": props.get("amount", ""),
                "description": props.get("description", ""),
                "source": props.get("source", ""),
            }
        )
    annotations.sort(key=lambda item: item["date"])
    return annotations


def _sse_stream(token_stream: Iterable[str], metadata: dict) -> StreamingResponse:
    def events():
        yield _sse_event("metadata", metadata)
        queue: Queue[tuple[str, str | Exception | None]] = Queue()
        collected: list[str] = []

        def collect_tokens() -> None:
            try:
                for token in token_stream:
                    if token:
                        queue.put(("token", str(token)))
                queue.put(("done", None))
            except Exception as exc:
                queue.put(("error", exc))

        Thread(target=collect_tokens, daemon=True).start()

        while True:
            try:
                event_type, value = queue.get(timeout=SSE_HEARTBEAT_SECONDS)
            except Empty:
                yield _sse_event("ping", {"status": "waiting"})
                continue

            if event_type == "token" and isinstance(value, str):
                collected.append(value)
                yield _sse_event("delta", {"text": value})
                continue

            if event_type == "done":
                yield _sse_event("done", {"text": "".join(collected)})
                break

            if event_type == "error":
                logger.warning("SSE stream failed: %s", value, exc_info=isinstance(value, BaseException))
                yield _sse_event(
                    "error",
                    {"error": "llm_error", "message": _sanitize_llm_error_message(str(value))},
                )
                break

    return StreamingResponse(events(), media_type="text/event-stream")


def _graph_tool_calls(entity: str) -> list[dict]:
    return [
        {
            "id": "open-company-profile",
            "label": "查看企业画像",
            "description": "打开企业画像、风险标记和证据边详情。",
            "method": "GET",
            "endpoint": f"/graph/company/{entity}",
        },
        {
            "id": "open-subgraph",
            "label": "展开关系子图",
            "description": "查看该实体 2 跳内的节点、关系和证据。",
            "method": "GET",
            "endpoint": "/graph/subgraph",
            "params": {"entity": entity, "depth": 2, "limit": 80},
        },
        {
            "id": "ask-hybrid-followup",
            "label": "追问文档证据",
            "description": "用 Hybrid RAG 针对该实体继续追问。",
            "method": "POST",
            "endpoint": "/qa/hybrid-rag/stream",
            "body": {"entity": entity},
            "stream": True,
        },
    ]


def _stock_tool_calls(target: dict) -> list[dict]:
    stock_code = str(target.get("stock_code") or "")
    company_name = str(target.get("company_name") or stock_code)
    return [
        {
            "id": "open-kline-events",
            "label": "查看K线事件",
            "description": "打开行情 K 线和证据线索标注。",
            "method": "GET",
            "endpoint": f"/market/kline/{stock_code}",
            "params": {"market": "A", "period": "daily"},
        },
        {
            "id": "open-company-profile",
            "label": "查看关联图谱",
            "description": "查看上市主体的图谱画像与证据边。",
            "method": "GET",
            "endpoint": f"/graph/company/{company_name}",
        },
        {
            "id": "refresh-news-context",
            "label": "补充证据线索",
            "description": "重新补充证据线索并返回结构化研判。",
            "method": "POST",
            "endpoint": "/analysis/stock",
            "body": {"stock_code": stock_code, "company_name": company_name, "refresh_news": True},
        },
    ]


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
