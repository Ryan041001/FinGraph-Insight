from datetime import datetime

from app.models.api import JobRun


def run_akshare_update_mock() -> JobRun:
    now = datetime.now().isoformat(timespec="seconds")
    return JobRun(
        job_run_id=f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        status="success",
        started_at=now,
        finished_at=now,
        new_documents=2,
        new_entities=3,
        new_relationships=4,
        failed_items=0,
    )
