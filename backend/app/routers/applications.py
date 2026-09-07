from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.agent import runs as agent_runs
from app.agent.session import is_run_active
from app.db import get_db
from app.models.application import Application, ApplicationStatus
from app.models.job import Job, RoleType
from app.schemas.agent_run import AgentRunRead
from app.schemas.application import (
    ApplicationDetail,
    ApplicationListItem,
    CoverLetterSummary,
    JobSummary,
    NotesUpdate,
    ResumeVersionSummary,
    StatusUpdate,
)
from app.tracking.state_machine import InvalidTransition, transition

router = APIRouter(tags=["applications"])

DELETABLE_STATUSES = {ApplicationStatus.discovered, ApplicationStatus.queued, ApplicationStatus.withdrawn}
# Statuses from which the autofill agent may start (prepared materials, not yet
# submitted).
AUTOFILL_STATUSES = {ApplicationStatus.queued, ApplicationStatus.in_progress}


def _job_summary(job: Job) -> JobSummary:
    return JobSummary(
        id=job.id, title=job.title, company_name=job.company.name, url=job.url, score=job.score, role_type=job.role_type
    )


def _list_item(application: Application) -> ApplicationListItem:
    return ApplicationListItem(
        id=application.id,
        job_id=application.job_id,
        status=application.status,
        resume_version_id=application.resume_version_id,
        cover_letter_id=application.cover_letter_id,
        submitted_at=application.submitted_at,
        notes=application.notes,
        created_at=application.created_at,
        updated_at=application.updated_at,
        job=_job_summary(application.job),
    )


def _detail(application: Application) -> ApplicationDetail:
    return ApplicationDetail(
        id=application.id,
        job_id=application.job_id,
        status=application.status,
        submitted_at=application.submitted_at,
        notes=application.notes,
        status_history=application.status_history,
        created_at=application.created_at,
        updated_at=application.updated_at,
        job=application.job,
        resume_version=(
            ResumeVersionSummary.model_validate(application.resume_version)
            if application.resume_version
            else None
        ),
        cover_letter=(
            CoverLetterSummary.model_validate(application.cover_letter) if application.cover_letter else None
        ),
    )


@router.get("/applications", response_model=list[ApplicationListItem])
def list_applications(
    status: list[ApplicationStatus] | None = Query(None),
    role_type: RoleType | None = None,
    company_id: int | None = None,
    has_cover_letter: bool | None = None,
    submitted_after: datetime | None = None,
    submitted_before: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Application).options(joinedload(Application.job).joinedload(Job.company))

    if status:
        query = query.filter(Application.status.in_(status))
    if role_type is not None:
        query = query.join(Job, Application.job_id == Job.id).filter(Job.role_type == role_type)
    if company_id is not None:
        query = query.join(Job, Application.job_id == Job.id).filter(Job.company_id == company_id)
    if has_cover_letter is not None:
        if has_cover_letter:
            query = query.filter(Application.cover_letter_id.isnot(None))
        else:
            query = query.filter(Application.cover_letter_id.is_(None))
    if submitted_after is not None:
        query = query.filter(Application.submitted_at >= submitted_after)
    if submitted_before is not None:
        query = query.filter(Application.submitted_at <= submitted_before)

    query = query.order_by(Application.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    return [_list_item(a) for a in query.all()]


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: int, db: Session = Depends(get_db)):
    application = (
        db.query(Application)
        .options(
            joinedload(Application.job).joinedload(Job.company),
            joinedload(Application.resume_version),
            joinedload(Application.cover_letter),
        )
        .filter(Application.id == application_id)
        .one_or_none()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return _detail(application)


@router.patch("/applications/{application_id}/status", response_model=ApplicationDetail)
def update_application_status(application_id: int, payload: StatusUpdate, db: Session = Depends(get_db)):
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    try:
        transition(application, payload.status, note=payload.note, force=payload.force)
    except InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    db.commit()
    db.refresh(application)
    return _detail(application)


@router.patch("/applications/{application_id}/notes", response_model=ApplicationDetail)
def update_application_notes(application_id: int, payload: NotesUpdate, db: Session = Depends(get_db)):
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    application.notes = payload.notes
    db.commit()
    db.refresh(application)
    return _detail(application)


@router.post("/jobs/{job_id}/queue", response_model=ApplicationDetail)
def queue_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    application = db.query(Application).filter(Application.job_id == job_id).one_or_none()
    if application is None:
        application = Application(job_id=job_id)
        db.add(application)
        db.flush()

    if application.status == ApplicationStatus.discovered:
        transition(application, ApplicationStatus.queued)

    db.commit()
    db.refresh(application)
    return _detail(application)


@router.post("/applications/{application_id}/autofill", response_model=AgentRunRead, status_code=202)
async def autofill_application(application_id: int, db: Session = Depends(get_db)):
    """Kick off the semi-autonomous form-filling agent for this application.
    Validates status + materials, enforces the global single-active-run guard,
    creates an AgentRun, launches it in the background, and returns the run
    immediately. The agent never submits - it stops at the review step."""
    application = (
        db.query(Application)
        .options(joinedload(Application.resume_version))
        .filter(Application.id == application_id)
        .one_or_none()
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.status not in AUTOFILL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Autofill requires status queued or in_progress (is {application.status.value!r})",
        )
    if application.resume_version is None or not application.resume_version.pdf_path:
        raise HTTPException(
            status_code=409,
            detail="Autofill requires a prepared resume with a compiled PDF - run Prepare first",
        )
    if is_run_active(db):
        raise HTTPException(
            status_code=409,
            detail="Another agent run is already active (the browser is a shared resource)",
        )

    run = agent_runs.create_run(db, application_id)
    agent_runs.schedule(run.id)
    return AgentRunRead.model_validate(run)


@router.delete("/applications/{application_id}", status_code=204)
def delete_application(application_id: int, db: Session = Depends(get_db)):
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.status not in DELETABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete an application in status {application.status.value!r}",
        )

    db.delete(application)
    db.commit()
