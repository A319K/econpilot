import asyncio
import random
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.discovery.ats_probe import resolve_unknown_companies
from app.discovery.base import RawJob, SourceError
from app.discovery.pipeline import (
    classify_job_family,
    classify_role_type,
    find_company,
    ingest_raw_job,
)
from app.discovery.scoring import score
from app.discovery.sources.ashby import AshbySource
from app.discovery.sources.github_repo import GithubNewGradSource, GithubRepoSource
from app.discovery.sources.greenhouse import GreenhouseSource
from app.discovery.sources.lever import LeverSource
from app.models.company import AtsType, Company
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.profile import get_profile

# Sources with a working client, keyed by Company.ats_type. Companies with
# ats_type other/unknown are not scannable yet and are skipped.
#
# Workday is intentionally omitted: its per-tenant pagination (up to ~25
# sequential requests) plus aggressive rate-limiting made a full sweep of the
# ~1,100 Workday tenants take 20+ minutes, which never finished inside a scan
# request and — since the scan commits only at the end — saved nothing. For
# internships we now rely on the GitHub Simplify tracker (see run_scan), which
# aggregates the same postings far more cheaply.
_ATS_SOURCE_MAP = {
    AtsType.greenhouse: GreenhouseSource,
    AtsType.lever: LeverSource,
    AtsType.ashby: AshbySource,
}


class ScanReport(BaseModel):
    companies_scanned: int = 0
    resolved_companies: int = 0
    jobs_found: int = 0
    new: int = 0
    duplicates: int = 0
    stale: int = 0
    filtered: int = 0
    errors: list[str] = []

    # Populated by run_scan regardless of caller; cheap to always fill in and
    # lets callers like app.discovery.watch build on top without re-fetching.
    new_job_ids: list[int] = []
    # company_id -> ids of ATS-sourced jobs seen this scan (i.e. present in
    # this company's fetch results after role-type filtering). Only populated
    # for companies whose fetch succeeded - absence of evidence from an
    # errored company must never be treated as "job vanished".
    seen_job_ids_by_company: dict[int, list[int]] = {}
    errored_company_ids: list[int] = []


def _classify_raw_role_type(raw: RawJob) -> RoleType:
    if raw.source == JobSource.github_repo:
        return RoleType.internship
    if raw.source == JobSource.github_newgrad:
        return RoleType.full_time
    return classify_role_type(raw.title)


def _role_type_matches(raw: RawJob, role_type: str) -> bool:
    return role_type == "all" or _classify_raw_role_type(raw).value == role_type


def _is_tech_noise(raw: RawJob) -> bool:
    """Full-time roles that classify to the 'other' family are the non-tech bulk
    (retail/finance/HR) big ATS tenants list alongside engineering. Internships
    are always kept (low volume, and intern titles often under-classify)."""
    if _classify_raw_role_type(raw) == RoleType.internship:
        return False
    return classify_job_family(raw.title) == JobFamily.other


def _freshness_cutoff(max_age_days: int | None) -> datetime | None:
    """Naive-UTC datetime before which jobs are considered stale, or None when
    the filter is disabled (max_age_days falsy / non-positive)."""
    if not max_age_days or max_age_days <= 0:
        return None
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=max_age_days)


def _is_fresh(raw: RawJob, cutoff: datetime | None) -> bool:
    """True if the job is newer than the cutoff. Jobs with no posted_at are
    kept (we can't date them, so we don't drop them). Timezone-aware
    posted_at values are normalized to naive UTC before comparing."""
    if cutoff is None or raw.posted_at is None:
        return True
    posted = raw.posted_at
    if posted.tzinfo is not None:
        posted = posted.astimezone(timezone.utc).replace(tzinfo=None)
    return posted >= cutoff


async def _fetch_for_company(
    company: Company, semaphore: asyncio.Semaphore, jitter_seconds: float = 0.0
) -> tuple[Company, list[RawJob], str | None]:
    source_cls = _ATS_SOURCE_MAP.get(company.ats_type)
    if source_cls is None:
        return company, [], None

    client = source_cls()
    async with semaphore:
        if jitter_seconds > 0:
            await asyncio.sleep(random.uniform(0, jitter_seconds))
        try:
            jobs = await client.fetch(company)
            return company, jobs, None
        except SourceError as exc:
            return company, [], str(exc)


def _rescore(db: Session, job: Job, company: Company, profile) -> None:
    job.score, job.score_breakdown = score(job, profile, company)


async def run_scan(
    db: Session,
    role_type: str = "all",
    targets_only: bool = False,
    jitter_seconds: float = 0.0,
    max_age_days: int | None = None,
) -> ScanReport:
    settings = get_settings()
    profile = get_profile()
    report = ScanReport()

    # Freshness cutoff: fall back to the configured default when the caller
    # doesn't override it. Computed once so every job in the scan is measured
    # against the same instant.
    effective_max_age = settings.scan_max_age_days if max_age_days is None else max_age_days
    cutoff = _freshness_cutoff(effective_max_age)

    # Internships are sourced entirely from the GitHub Simplify tracker below:
    # it aggregates the same postings the company ATS sweep would find, but in a
    # single cheap fetch instead of a 20+ minute per-tenant crawl. So an
    # internship-only scan skips the ATS sweep (and the ATS auto-resolve that
    # only serves it) and falls straight through to the GitHub source.
    scan_ats = role_type != "internship"

    # Turn companies we only know by name into scannable ones by resolving their
    # ATS against the job-board APIs. Runs before the company query below so any
    # newly-resolved company is included in this same scan. Each company is
    # probed at most once per reprobe window, so this is cheap after the first
    # pass. Failures here must never abort the scan itself.
    if scan_ats and settings.discovery_auto_resolve_ats:
        try:
            resolved = await resolve_unknown_companies(
                db, reprobe_after_days=settings.ats_reprobe_after_days
            )
            if resolved["resolved"]:
                report.resolved_companies = int(resolved["resolved"])
        except Exception as exc:  # noqa: BLE001 - resolution is best-effort
            report.errors.append(f"ats auto-resolve: {exc}")

    companies: list[Company] = []
    if scan_ats:
        query = db.query(Company).filter(Company.ats_type != AtsType.unknown)
        if targets_only:
            query = query.filter(Company.is_target.is_(True))
        companies = query.all()

    semaphore = asyncio.Semaphore(settings.scan_concurrency)
    company_results = await asyncio.gather(
        *[_fetch_for_company(company, semaphore, jitter_seconds) for company in companies]
    )

    for company, raw_jobs, error in company_results:
        report.companies_scanned += 1
        if error:
            report.errors.append(f"{company.name}: {error}")
            report.errored_company_ids.append(company.id)
            continue

        seen_ids: list[int] = []
        for raw in raw_jobs:
            report.jobs_found += 1
            if not _role_type_matches(raw, role_type):
                continue
            if settings.discovery_tech_only and _is_tech_noise(raw):
                report.filtered += 1
                continue
            if not _is_fresh(raw, cutoff):
                report.stale += 1
                continue

            job, created = ingest_raw_job(db, raw, known_company=company)
            _rescore(db, job, company, profile)
            seen_ids.append(job.id)
            if created:
                report.new += 1
                report.new_job_ids.append(job.id)
            else:
                report.duplicates += 1
        report.seen_job_ids_by_company[company.id] = seen_ids

    if role_type in ("all", "internship"):
        github_client = GithubRepoSource()
        try:
            github_jobs = await github_client.fetch(None)
        except SourceError as exc:
            github_jobs = []
            report.errors.append(f"github_repo: {exc}")

        for raw in github_jobs:
            report.jobs_found += 1

            known_company = find_company(db, raw.company_name)
            if targets_only and (known_company is None or not known_company.is_target):
                continue
            if not _is_fresh(raw, cutoff):
                report.stale += 1
                continue

            job, created = ingest_raw_job(db, raw, known_company=known_company)
            _rescore(db, job, job.company, profile)
            if created:
                report.new += 1
                report.new_job_ids.append(job.id)
            else:
                report.duplicates += 1

    if role_type in ("all", "full_time"):
        newgrad_client = GithubNewGradSource()
        try:
            newgrad_jobs = await newgrad_client.fetch(None)
        except SourceError as exc:
            newgrad_jobs = []
            report.errors.append(f"github_newgrad: {exc}")

        for raw in newgrad_jobs:
            report.jobs_found += 1

            known_company = find_company(db, raw.company_name)
            if targets_only and (known_company is None or not known_company.is_target):
                continue
            # New-grad postings are full-time, so the tech-only noise filter
            # applies the same way it does to ATS-sourced full-time roles.
            if settings.discovery_tech_only and _is_tech_noise(raw):
                report.filtered += 1
                continue
            if not _is_fresh(raw, cutoff):
                report.stale += 1
                continue

            job, created = ingest_raw_job(db, raw, known_company=known_company)
            _rescore(db, job, job.company, profile)
            if created:
                report.new += 1
                report.new_job_ids.append(job.id)
            else:
                report.duplicates += 1

    db.commit()
    return report
