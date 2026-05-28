from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.data.financial_dataset_loader import load_financial_dataset_directory
from app.models.api import ExtractRequest, HealthResponse, Text2CypherRequest, Text2CypherSafety
from app.services.extraction_service import extract_mock, extract_with_deepseek, judge_extraction_with_deepseek
from app.services.graph_rag_service import answer_with_deepseek_graph_context, answer_with_graph_context
from app.services.graph_query_service import company_profile, paths, subgraph
from app.services.graph_runtime import import_graph_runtime
from app.services.graph_store import graph_store
from app.services.market_service import build_kline_response, get_kline_mock
from app.services.metrics_service import default_gold_standard_path, evaluate_gold_standard
from app.services.mock_data import sample_graph
from app.services.scheduler_service import get_job_run, list_job_runs, run_akshare_update_mock
from app.services.stock_analysis_service import build_stock_analysis
from app.services.llm_service import HttpLLMGateway
from app.services.text2cypher_service import answer_text2cypher, generate_cypher_with_deepseek


app = FastAPI(title="Financial KG API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", neo4j=graph_store.health_status(), scheduler="running")


@app.post("/datasets/import")
def import_dataset(payload: dict | None = None) -> dict:
    dataset = (payload or {}).get("dataset", "sample_graph")
    if dataset not in {"sample_graph", "financial_datasets"}:
        raise HTTPException(status_code=400, detail={"error": "invalid_input", "message": f"unsupported dataset: {dataset}"})

    graph = _load_dataset_graph(dataset)
    stats = import_graph_runtime(graph)
    return {
        "import_run_id": "import_sample_graph",
        "nodes_created": stats.nodes_created,
        "relationships_created": stats.relationships_created,
        "nodes_skipped": stats.nodes_matched,
        "relationships_skipped": stats.relationships_skipped,
        "status": "success",
    }


def _load_dataset_graph(dataset: str):
    if dataset == "financial_datasets":
        project_root = Path(__file__).resolve().parents[2]
        raw_dataset_path = project_root / "data" / "raw" / "FinancialDatasets"
        fallback_path = project_root / "data" / "processed"
        graph = load_financial_dataset_directory(raw_dataset_path if raw_dataset_path.exists() else fallback_path)
        if graph.nodes:
            return graph
    return sample_graph("示例科技")


@app.post("/extract")
def extract(request: ExtractRequest) -> dict:
    if settings.llm_enabled:
        try:
            gateway = HttpLLMGateway()
            payload = extract_with_deepseek(request.text, gateway)
            if request.options.judge:
                payload = judge_extraction_with_deepseek(payload, gateway)
            return payload
        except Exception as exc:
            fallback = extract_mock(request.text)
            fallback["warnings"].append(f"llm_fallback: {exc}")
            return fallback
    return extract_mock(request.text)


@app.post("/graph/import")
def import_graph(payload: dict) -> dict:
    stats = graph_store.import_extraction_payload(payload)
    return {
        "nodes_created": stats.nodes_created,
        "nodes_matched": stats.nodes_matched,
        "relationships_created": stats.relationships_created,
        "relationships_skipped": stats.relationships_skipped,
        "status": "success",
    }


@app.get("/graph/company/{name}")
def get_company_profile(name: str, depth: int = 2, include_pending: bool = False) -> dict:
    return company_profile(name, depth=depth)


@app.get("/graph/subgraph")
def get_subgraph(entity: str, depth: int = 2, limit: int = 80) -> dict:
    return subgraph(entity, depth=depth, limit=limit)


@app.get("/graph/path")
def get_path(source: str, target: str, max_depth: int = 4) -> dict:
    return paths(source, target, max_depth=max_depth)


@app.post("/qa/graph-rag")
def graph_rag(payload: dict) -> dict:
    company_name = extract_company_name_from_question(payload.get("question"))
    graph = graph_store.subgraph(company_name)
    if settings.llm_enabled:
        try:
            return answer_with_deepseek_graph_context(str(payload.get("question", "")), graph, HttpLLMGateway())
        except Exception:
            pass
    return answer_with_graph_context(str(payload.get("question", "")), graph)


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

    return "该企业"


@app.post("/qa/text2cypher")
def text2cypher(request: Text2CypherRequest):
    try:
        if settings.llm_enabled:
            cypher, rules = generate_cypher_with_deepseek(request.question, HttpLLMGateway())
            return {
                "cypher": cypher,
                "safety": Text2CypherSafety(passed=True, rules=rules).model_dump(),
                "table": {"columns": [], "rows": []},
                "graph": sample_graph().model_dump(),
            }
        return answer_text2cypher(request.question)
    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": "unsafe_cypher",
                "message": str(exc),
                "cypher": "",
            },
        )


@app.get("/jobs")
def list_jobs() -> dict:
    return {"jobs": [job.model_dump() for job in list_job_runs()]}


@app.post("/jobs/akshare/run")
def run_akshare_job() -> dict:
    return run_akshare_update_mock().model_dump()


@app.get("/jobs/{job_run_id}")
def get_job(job_run_id: str) -> dict:
    job = get_job_run(job_run_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "scheduler_error", "message": "job run not found"})
    return job.model_dump()


@app.get("/metrics/extraction")
def extraction_metrics() -> dict:
    return evaluate_gold_standard(default_gold_standard_path())


@app.post("/metrics/evaluate")
def evaluate_metrics() -> dict:
    return extraction_metrics()


@app.post("/analysis/stock")
def stock_analysis(payload: dict) -> dict:
    if settings.llm_enabled and payload.get("refresh_news"):
        return build_stock_analysis(payload, news_gateway=HttpLLMGateway())
    return build_stock_analysis(payload)


@app.get("/analysis/stock/{stock_code}/latest")
def latest_stock_analysis(stock_code: str) -> dict:
    return stock_analysis({"stock_code": stock_code, "company_name": "示例科技"})


@app.get("/market/kline/{stock_code}")
def get_market_kline(
    stock_code: str,
    market: str = "A",
    period: str = "daily",
    start_date: str | None = None,
    end_date: str | None = None,
    adjust: str = "qfq",
) -> dict:
    if settings.market_live_enabled:
        return build_kline_response(
            stock_code=stock_code,
            market=market,
            period=period,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
        )
    return get_kline_mock(
        stock_code=stock_code,
        market=market,
        period=period,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )
