from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.discovery.base import RawJob
from app.discovery.pipeline import get_or_create_company, ingest_raw_job
from app.discovery.scoring import score
from app.materials.prepare import PrepareError, prepare_materials
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.profile import get_profile
from app.schemas.job import JobRead, ManualJobCreate
from app.schemas.prepare import PrepareReport, PrepareRequest

router = APIRouter(tags=["jobs"])


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(
    role_type: RoleType | None = None,
    job_family: JobFamily | None = None,
    min_score: float | None = None,
    source: JobSource | None = None,
    location: str | None = None,
    is_active: bool | None = None,
    company_id: int | None = None,
    discovered_after: datetime | None = None,
    sort: Literal["score", "recent"] = "score",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Job)

    if role_type is not None:
        query = query.filter(Job.role_type == role_type)
    if job_family is not None:
        query = query.filter(Job.job_family == job_family)
    if min_score is not None:
        query = query.filter(Job.score >= min_score)
    if source is not None:
        query = query.filter(Job.source == source)
    if location:
        # Locations arrive as free text from every ATS ("New York, NY",
        # "Boston, MA (Hybrid)", "Remote - US"), so this is a case-insensitive
        # substring match rather than an equality check against a fixed list.
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if is_active is not None:
        query = query.filter(Job.is_active == is_active)
    if company_id is not None:
        query = query.filter(Job.company_id == company_id)
    if discovered_after is not None:
        query = query.filter(Job.discovered_at >= discovered_after)

    # "recent" orders by how old the posting actually is, matching the age
    # column in the queue (which shows posted_at, falling back to discovered_at).
    # Ordering by discovered_at alone put a whole scan batch on one timestamp and
    # left the visible ages scrambled. Score breaks ties.
    if sort == "recent":
        query = query.order_by(
            func.coalesce(Job.posted_at, Job.discovered_at).desc(),
            Job.score.desc(),
        )
    else:
        query = query.order_by(Job.score.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    return query.all()


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/manual", response_model=JobRead, status_code=201)
def create_manual_job(payload: ManualJobCreate, db: Session = Depends(get_db)):
    company_name = payload.company_name or "Unknown"
    company = get_or_create_company(db, company_name)

    raw = RawJob(
        title=payload.title or payload.url,
        url=payload.url,
        location=None,
        # Job has no dedicated notes column; store any supplied notes as the
        # description since that's the closest free-text field available.
        description=payload.notes or "",
        posted_at=None,
        source=JobSource.manual,
        company_name=company.name,
    )

    job, _ = ingest_raw_job(db, raw, known_company=company, role_type_override=payload.role_type)

    profile = get_profile()
    job.score, job.score_breakdown = score(job, profile, company)

    db.commit()
    db.refresh(job)
    return job


@router.post("/jobs/{job_id}/prepare", response_model=PrepareReport)
async def prepare_job_materials(
    job_id: int, payload: PrepareRequest = PrepareRequest(), db: Session = Depends(get_db)
):
    try:
        return await prepare_materials(db, job_id, tailor=payload.tailor, cover_letter=payload.cover_letter)
    except PrepareError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
