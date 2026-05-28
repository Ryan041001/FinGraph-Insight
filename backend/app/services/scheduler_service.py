from datetime import datetime
from collections.abc import Callable

from app.models.api import JobRun
from app.data.akshare_fetcher import fetch_akshare_news

_job_runs: dict[str, JobRun] = {}


def run_akshare_update(fetcher: Callable[[], list[dict[str, str]]] = fetch_akshare_news) -> JobRun:
    now = datetime.now().isoformat(timespec="seconds")
    failed_items = 0
    try:
        documents = fetcher()
    except Exception:
        documents = []
        failed_items = 1

    job = JobRun(
        job_run_id=f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        status="success",
        started_at=now,
        finished_at=now,
        new_documents=len(documents),
        new_entities=0,
        new_relationships=0,
        failed_items=failed_items,
    )
    _job_runs[job.job_run_id] = job
    return job


def run_akshare_update_mock() -> JobRun:
    return run_akshare_update()


def list_job_runs() -> list[JobRun]:
    return list(_job_runs.values())


def get_job_run(job_run_id: str) -> JobRun | None:
    return _job_runs.get(job_run_id)
