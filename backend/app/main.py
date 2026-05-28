from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.models.api import ExtractRequest, HealthResponse, Text2CypherRequest
from app.services.extraction_service import extract_mock
from app.services.graph_query_service import company_profile
from app.services.market_service import get_kline_mock
from app.services.mock_data import sample_graph
from app.services.scheduler_service import run_akshare_update_mock
from app.services.text2cypher_service import answer_text2cypher


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
    return HealthResponse(status="ok", neo4j="mock", scheduler="mock")


@app.post("/datasets/import")
def import_dataset() -> dict:
    return {
        "import_run_id": "import_mock",
        "nodes_created": 3,
        "relationships_created": 2,
        "nodes_skipped": 0,
        "relationships_skipped": 0,
        "status": "success",
    }


@app.post("/extract")
def extract(request: ExtractRequest) -> dict:
    return extract_mock(request.text)


@app.post("/graph/import")
def import_graph() -> dict:
    return {
        "nodes_created": 2,
        "nodes_matched": 1,
        "relationships_created": 1,
        "relationships_skipped": 0,
        "status": "success",
    }


@app.get("/graph/company/{name}")
def get_company_profile(name: str, depth: int = 2, include_pending: bool = False) -> dict:
    return company_profile(name, depth=depth)


@app.get("/graph/subgraph")
def get_subgraph(entity: str, depth: int = 2, limit: int = 80) -> dict:
    return sample_graph(entity).model_dump()


@app.get("/graph/path")
def get_path(source: str, target: str, max_depth: int = 4) -> dict:
    graph = sample_graph(source)
    return {"paths": [{"nodes": graph.model_dump()["nodes"], "edges": graph.model_dump()["edges"], "length": 2}]}


@app.post("/qa/graph-rag")
def graph_rag(payload: dict) -> dict:
    company_name = extract_company_name_from_question(payload.get("question"))
    graph = sample_graph(company_name)
    return {
        "answer": f"{company_name}与红杉资本存在B轮融资相关路径，建议重点复核资金来源、轮次信息和后续关联方变化。",
        "entities": [company_name, "红杉资本", "B轮融资事件"],
        "supporting_graph": graph.model_dump(),
        "citations": [{"source": "图谱来源", "source_text": f"红杉资本参与了{company_name}B轮融资。"}],
    }


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
    return {"jobs": []}


@app.post("/jobs/akshare/run")
def run_akshare_job() -> dict:
    return run_akshare_update_mock().model_dump()


@app.get("/jobs/{job_run_id}")
def get_job(job_run_id: str) -> dict:
    job = run_akshare_update_mock().model_dump()
    job["job_run_id"] = job_run_id
    return job


@app.get("/metrics/extraction")
def extraction_metrics() -> dict:
    return {
        "entity_precision": 0.82,
        "entity_recall": 0.78,
        "entity_f1": 0.80,
        "relation_precision": 0.76,
        "relation_recall": 0.70,
        "relation_f1": 0.73,
        "hallucination_rate": 0.08,
    }


@app.post("/metrics/evaluate")
def evaluate_metrics() -> dict:
    return extraction_metrics()


@app.post("/analysis/stock")
def stock_analysis(payload: dict) -> dict:
    graph = sample_graph(payload.get("company_name") or payload.get("stock_code") or "示例科技")
    return {
        "target": {"stock_code": payload.get("stock_code", "600000"), "company_name": payload.get("company_name", "示例科技")},
        "fundamentals": {"industry": "金融科技", "data_time": "mock"},
        "news_events": [],
        "subgraph": graph.model_dump(),
        "analysis": {
            "summary": "该示例公司当前主要关注融资事件和关联方变化。",
            "opportunity_factors": [],
            "risk_factors": [],
            "graph_insights": [{"title": "融资事件可由图谱路径追溯", "path": "红杉资本 -> B轮融资事件 -> 示例科技"}],
            "confidence": 0.75,
            "missing_data": ["真实行情和财务数据尚未接入"],
            "disclaimer": "本结果仅用于课程项目演示和研究辅助，不构成投资建议。",
        },
    }


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
    return get_kline_mock(
        stock_code=stock_code,
        market=market,
        period=period,
        start_date=start_date,
        end_date=end_date,
        adjust=adjust,
    )
