from collections import OrderedDict
from collections.abc import Callable
from threading import RLock

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.models.api import JobRun
from app.data.akshare_fetcher import fetch_akshare_news
from app.services.extraction_service import extract_with_llm, judge_extraction_with_llm
from app.services.graph_runtime import import_extraction_payload_runtime
from app.services.graph_store import ImportStats
from app.services.llm_service import HttpLLMGateway
from app.services.pipeline_service import run_extraction_pipeline

_job_runs: "OrderedDict[str, JobRun]" = OrderedDict()
_job_runs_lock = RLock()
_scheduler: BackgroundScheduler | None = None


def _record_job_run(job: JobRun) -> None:
    max_size = max(1, settings.job_run_history_max_size)
    with _job_runs_lock:
        _job_runs[job.job_run_id] = job
        _job_runs.move_to_end(job.job_run_id)
        while len(_job_runs) > max_size:
            _job_runs.popitem(last=False)


def run_akshare_update(
    fetcher: Callable[[], list[dict[str, str]]] = fetch_akshare_news,
    extractor: Callable[[str], dict] | None = None,
    judge: Callable[[dict], dict] | None = None,
    importer: Callable[[dict], ImportStats] = import_extraction_payload_runtime,
) -> JobRun:
    job = run_extraction_pipeline(
        fetcher=fetcher,
        extractor=extractor or _default_extractor,
        judge=judge or _default_judge,
        importer=importer,
    )
    _record_job_run(job)
    return job


def list_job_runs() -> list[JobRun]:
    with _job_runs_lock:
        return list(_job_runs.values())


def get_job_run(job_run_id: str) -> JobRun | None:
    with _job_runs_lock:
        return _job_runs.get(job_run_id)


def build_akshare_scheduler(
    fetcher: Callable[[], list[dict[str, str]]] = fetch_akshare_news,
) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        lambda: run_akshare_update(fetcher=fetcher),
        trigger=CronTrigger.from_crontab(settings.akshare_update_cron),
        id="akshare_update",
        replace_existing=True,
    )
    return scheduler


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not settings.scheduler_enabled:
        return None
    if _scheduler and _scheduler.running:
        return _scheduler
    _scheduler = build_akshare_scheduler()
    _scheduler.start()
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def scheduler_status() -> str:
    if not settings.scheduler_enabled:
        return "disabled"
    if _scheduler and _scheduler.running:
        return "running"
    return "configured"


def _default_extractor(text: str) -> dict:
    return extract_with_llm(text, HttpLLMGateway())


def _default_judge(payload: dict) -> dict:
    return judge_extraction_with_llm(payload, HttpLLMGateway())
