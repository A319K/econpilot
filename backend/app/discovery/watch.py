import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.discovery.scan import _ATS_SOURCE_MAP, ScanReport, run_scan
from app.models.company import Company
from app.models.job import Job, JobSource
from app.notify.factory import get_notifier

logger = logging.getLogger(__name__)

NotifyFn = Callable[[str, str], Awaitable[bool]]

_MAX_NOTIFY_LINES = 10


class WatchReport(BaseModel):
    companies_scanned: int = 0
    jobs_found: int = 0
    new: int = 0
    duplicates: int = 0
    errors: list[str] = []
    deactivated: int = 0
    notified: int = 0


def _deactivate_vanished(db: Session, scan: ScanReport) -> int:
    """Mark inactive any active ATS-sourced Job whose company was scanned
    successfully this cycle but whose job id did not appear in this scan's
    results. Companies whose fetch errored, or whose ats_type has no working
    source client (so an "empty" result proves nothing), are skipped -
    absence of evidence is not evidence of absence.
    """
    deactivated = 0

    for company_id, seen_ids in scan.seen_job_ids_by_company.items():
        if company_id in scan.errored_company_ids:
            continue

        company = db.get(Company, company_id)
        if company is None or company.ats_type not in _ATS_SOURCE_MAP:
            continue

        source = JobSource(company.ats_type.value)
        stale = (
            db.query(Job)
            .filter(
                Job.company_id == company_id,
                Job.source == source,
                Job.is_active.is_(True),
                Job.id.notin_(seen_ids),
            )
            .all()
        )
        for job in stale:
            job.is_active = False
            deactivated += 1

    return deactivated


async def _notify_new_jobs(db: Session, scan: ScanReport, notify: NotifyFn) -> int:
    settings = get_settings()
    if not scan.new_job_ids:
        return 0

    candidates = (
        db.query(Job)
        .filter(
            Job.id.in_(scan.new_job_ids),
            Job.score >= settings.watch_notify_min_score,
            Job.notified_at.is_(None),
        )
        .order_by(Job.score.desc())
        .all()
    )
    if not candidates:
        return 0

    lines = []
    for job in candidates[:_MAX_NOTIFY_LINES]:
        lines.append(f"{job.score:.0f} | {job.company.name} | {job.title} | {job.url}")
    remaining = len(candidates) - _MAX_NOTIFY_LINES
    if remaining > 0:
        lines.append(f"and {remaining} more")

    subject = f"{len(candidates)} new target jobs"
    body = "\n".join(lines)

    now = datetime.now(timezone.utc)
    for job in candidates:
        job.notified_at = now
    db.flush()

    try:
        await notify(subject, body)
    except Exception:
        logger.exception("watch notification failed; scan results are unaffected")

    return len(candidates)


async def run_watch_scan(db: Session, notify: NotifyFn | None = None) -> WatchReport:
    if notify is None:
        notifier = get_notifier()
        notify = notifier.send

    scan = await run_scan(db, role_type="all", targets_only=True, jitter_seconds=2.0)

    deactivated = _deactivate_vanished(db, scan)
    notified = await _notify_new_jobs(db, scan, notify)
    db.commit()

    return WatchReport(
        companies_scanned=scan.companies_scanned,
        jobs_found=scan.jobs_found,
        new=scan.new,
        duplicates=scan.duplicates,
        errors=scan.errors,
        deactivated=deactivated,
        notified=notified,
    )
