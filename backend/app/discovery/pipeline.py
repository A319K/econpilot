import hashlib
import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import SOURCE_RANK, JOB_FAMILY_KEYWORDS
from app.discovery.ats_resolve import resolve_ats
from app.discovery.base import RawJob
from app.models.company import AtsType, Company
from app.models.job import Job, JobFamily, JobSource, RoleType

_PUNCT_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_REQ_ID_RE = re.compile(r"\(?\b[Rr]\d{4,}\b\)?")
_SEASON_RE = re.compile(r"\b(summer|fall|winter|spring)\b")
_INTERN_DASH_RE = re.compile(r"\bintern\s*-\s*")

_INTERNSHIP_RE = re.compile(r"\b(intern|internship|co-?op)\b", re.IGNORECASE)


def normalize_title(title: str) -> str:
    t = title.lower()
    t = _REQ_ID_RE.sub("", t)
    t = _YEAR_RE.sub("", t)
    t = _SEASON_RE.sub("", t)
    t = _INTERN_DASH_RE.sub("", t)
    t = _PUNCT_RE.sub(" ", t)
    t = _WHITESPACE_RE.sub(" ", t).strip()
    return t


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    t = value.lower()
    t = _PUNCT_RE.sub(" ", t)
    t = _WHITESPACE_RE.sub(" ", t).strip()
    return t


def compute_dedup_hash(company_name: str, title: str, location: str | None) -> str:
    normalized = "|".join(
        [normalize_text(company_name), normalize_title(title), normalize_text(location)]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def classify_role_type(title: str) -> RoleType:
    return RoleType.internship if _INTERNSHIP_RE.search(title) else RoleType.full_time


def classify_job_family(title: str) -> JobFamily:
    haystack = title.lower()
    for family, keywords in JOB_FAMILY_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return JobFamily(family)
    return JobFamily.other


def _source_rank(source: JobSource) -> int:
    return SOURCE_RANK.get(source.value, 0)


def find_company(db: Session, name: str) -> Company | None:
    return db.query(Company).filter(func.lower(Company.name) == name.lower()).one_or_none()


def get_or_create_company(db: Session, name: str) -> Company:
    existing = find_company(db, name)
    if existing is not None:
        return existing

    company = Company(name=name, ats_type=AtsType.unknown, is_target=False)
    db.add(company)
    db.flush()
    return company


# ATS types whose keyless list API needs a board id to be scannable at all.
_BOARD_ID_REQUIRED = {AtsType.greenhouse, AtsType.lever, AtsType.ashby, AtsType.workday}


def maybe_resolve_company_ats(company: Company, url: str | None) -> bool:
    """Upgrade a still-unknown company's ATS from an application URL so later
    scans can fetch it directly (turning discovered listings into a recurring
    source). Never overrides a company whose ATS is already known, and refuses
    to set a scannable ATS without the board id it requires (which would only
    produce a SourceError every cycle). Returns True if it changed anything."""
    if company.ats_type != AtsType.unknown:
        return False
    ats_type, board_id = resolve_ats(url)
    if ats_type == AtsType.unknown:
        return False
    if ats_type in _BOARD_ID_REQUIRED and not board_id:
        return False
    company.ats_type = ats_type
    if board_id:
        company.ats_board_id = board_id
    return True


class PipelineResult:
    def __init__(self) -> None:
        self.new: int = 0
        self.duplicates: int = 0

    def record(self, created: bool) -> None:
        if created:
            self.new += 1
        else:
            self.duplicates += 1


def ingest_raw_job(
    db: Session,
    raw: RawJob,
    known_company: Company | None = None,
    role_type_override: RoleType | None = None,
) -> tuple[Job, bool]:
    """Normalize, classify, dedup, and persist a single RawJob.

    Returns (job, created) where created=False means an existing row was
    matched (and possibly merged/upgraded) instead of a new one being made.
    """
    company = known_company or get_or_create_company(db, raw.company_name)
    # Turn a discovered listing into a recurring source: if we don't yet know
    # this company's ATS, derive it (and its board id) from the application URL.
    maybe_resolve_company_ats(company, raw.url)

    if role_type_override is not None:
        role_type = role_type_override
    elif raw.source == JobSource.github_repo:
        role_type = RoleType.internship
    elif raw.source == JobSource.github_newgrad:
        role_type = RoleType.full_time
    else:
        role_type = classify_role_type(raw.title)
    job_family = classify_job_family(raw.title)
    dedup_hash = compute_dedup_hash(company.name, raw.title, raw.location)

    existing = db.query(Job).filter(Job.dedup_hash == dedup_hash).one_or_none()
    if existing is None:
        existing = db.query(Job).filter(Job.url == raw.url).one_or_none()

    if existing is None:
        job = Job(
            company_id=company.id,
            title=raw.title,
            location=raw.location,
            url=raw.url,
            source=raw.source,
            role_type=role_type,
            job_family=job_family,
            description=raw.description,
            posted_at=raw.posted_at,
            dedup_hash=dedup_hash,
        )
        db.add(job)
        db.flush()
        return job, True

    if _source_rank(raw.source) > _source_rank(existing.source):
        existing.source = raw.source
        existing.url = raw.url
        existing.title = raw.title
        existing.role_type = role_type
        existing.job_family = job_family
        existing.description = raw.description or existing.description
        existing.location = raw.location or existing.location
        existing.posted_at = raw.posted_at or existing.posted_at
        existing.dedup_hash = dedup_hash
    else:
        existing.description = existing.description or raw.description
        existing.location = existing.location or raw.location
        existing.posted_at = existing.posted_at or raw.posted_at

    db.flush()
    return existing, False


def ingest_raw_jobs(
    db: Session, raw_jobs: list[RawJob], known_company: Company | None = None
) -> PipelineResult:
    result = PipelineResult()
    for raw in raw_jobs:
        _, created = ingest_raw_job(db, raw, known_company=known_company)
        result.record(created)
    return result
