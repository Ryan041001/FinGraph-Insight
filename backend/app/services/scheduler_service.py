from datetime import datetime

from app.models.api import JobRun

_job_runs: dict[str, JobRun] = {}


def run_akshare_update_mock() -> JobRun:
    now = datetime.now().isoformat(timespec="seconds")
    job = JobRun(
        job_run_id=f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        status="success",
        started_at=now,
        finished_at=now,
        new_documents=2,
        new_entities=3,
        new_relationships=4,
        failed_items=0,
    )
    _job_runs[job.job_run_id] = job
    return job


def list_job_runs() -> list[JobRun]:
    return list(_job_runs.values())


def get_job_run(job_run_id: str) -> JobRun | None:
    return _job_runs.get(job_run_id)
