from pathlib import Path
from contextlib import asynccontextmanager
import json
import re
from collections import OrderedDict
from collections.abc import Iterable
from queue import Empty, Queue
from threading import RLock, Thread
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse

from app.config import settings
from app.data.financial_dataset_loader import load_financial_dataset_directory
from app.models.api import DocumentIndexRequest, ExtractRequest, HealthResponse, Text2CypherRequest, Text2CypherSafety
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()
        close_neo4j_driver()


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
        project_root = Path(__file__).resolve().parents[2]
        candidate_paths = [
            project_root / "data" / "raw" / "FinancialDatasets",
            project_root / "data" / "processed",
        ]
        for dataset_path in candidate_paths:
            if not dataset_path.exists():
                continue
            graph = _load_dataset_graph_cached(dataset_path)
            if graph.nodes:
                return graph
    raise HTTPException(
        status_code=404,
        detail={"error": "dataset_not_found", "message": "financial dataset files were not found or produced no nodes"},
    )


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
        except Exception as exc:
            result = build_stock_analysis({**payload, "refresh_news": False})
            missing_data = result["analysis"].setdefault("missing_data", [])
            missing_data.append(f"新闻补充暂不可用，已使用本地图谱事件：{exc}")
    else:
        result = build_stock_analysis(payload)

    if use_llm:
        try:
            result = summarize_stock_analysis_with_llm(result, HttpLLMGateway())
        except Exception as exc:
            missing_data = result["analysis"].setdefault("missing_data", [])
            missing_data.append(f"模型研判暂不可用，已返回本地图谱摘要：{exc}")

    stock_code = str(result.get("target", {}).get("stock_code") or payload.get("stock_code") or "")
    if stock_code:
        _record_stock_analysis(stock_code, result)
    return result


@app.get("/analysis/stock/{stock_code}/latest")
def latest_stock_analysis(stock_code: str) -> dict:
    cached = _get_cached_stock_analysis(stock_code)
    if cached:
        return cached
    return build_stock_analysis({"stock_code": stock_code, "company_name": stock_code})


@app.post("/analysis/stock/stream")
def stock_analysis_stream(payload: dict) -> StreamingResponse:
    base = build_stock_analysis(payload)
    messages = [
        {
            "role": "system",
            "content": (
                "你是图谱增强金融研判助手。只能基于输入材料生成研究辅助摘要。"
                "直接输出适合前端逐字展示的中文文本，必须包含风险提示和免责声明，"
                "不得输出买入、卖出、目标价或收益承诺。"
                f"\n{HTML_CHAT_FORMAT_INSTRUCTIONS}"
            ),
        },
        {"role": "user", "content": json.dumps(base, ensure_ascii=False)},
    ]
    token_stream = HttpLLMGateway().stream_complete(
        task=LLMTask.STOCK_ANALYSIS_STREAM,
        messages=messages,
        temperature=0.1,
        max_tokens=2048,
    )
    return _sse_stream(
        token_stream,
        metadata={
            "target": base["target"],
            "fundamentals": base["fundamentals"],
            "news_events": base["news_events"],
            "subgraph": base["subgraph"],
            "tool_calls": _stock_tool_calls(base["target"]),
        },
    )


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
            "description": "打开行情 K 线和图谱事件标注。",
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
            "label": "补充新闻上下文",
            "description": "重新调用新闻补充并返回结构化研判。",
            "method": "POST",
            "endpoint": "/analysis/stock",
            "body": {"stock_code": stock_code, "company_name": company_name, "refresh_news": True},
        },
    ]


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
