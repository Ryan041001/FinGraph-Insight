from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime
from threading import RLock, Thread

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.logging_config import get_logger
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
logger = get_logger(__name__)


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


def start_akshare_update_async(
    fetcher: Callable[[], list[dict[str, str]]] = fetch_akshare_news,
    extractor: Callable[[str], dict] | None = None,
    judge: Callable[[dict], dict] | None = None,
    importer: Callable[[dict], ImportStats] = import_extraction_payload_runtime,
) -> JobRun:
    started_at = datetime.now().isoformat(timespec="seconds")
    job_run_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    initial = JobRun(
        job_run_id=job_run_id,
        status="running",
        started_at=started_at,
        finished_at=None,
        new_documents=0,
        new_entities=0,
        new_relationships=0,
        failed_items=0,
    )
    _record_job_run(initial)

    def worker() -> None:
        try:
            completed = run_extraction_pipeline(
                fetcher=fetcher,
                extractor=extractor or _default_extractor,
                judge=judge or _default_judge,
                importer=importer,
            )
            final = completed.model_copy(update={"job_run_id": job_run_id, "started_at": started_at})
            _record_job_run(final)
        except Exception:
            logger.exception("async akshare update job failed job_run_id=%s", job_run_id)
            _record_job_run(
                JobRun(
                    job_run_id=job_run_id,
                    status="failed",
                    started_at=started_at,
                    finished_at=datetime.now().isoformat(timespec="seconds"),
                    failed_items=1,
                )
            )

    Thread(target=worker, daemon=True).start()
    return initial


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
        max_instances=1,
        coalesce=True,
        misfire_grace_time=300,
    )
    scheduler.add_listener(_on_scheduler_event, EVENT_JOB_ERROR | EVENT_JOB_MISSED)
    return scheduler


def _on_scheduler_event(event) -> None:
    if getattr(event, "exception", None) is not None:
        logger.error(
            "scheduled job %s raised: %s",
            getattr(event, "job_id", "?"),
            event.exception,
            exc_info=(type(event.exception), event.exception, event.exception.__traceback__),
        )
    else:
        logger.warning("scheduled job %s missed its run time", getattr(event, "job_id", "?"))


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
