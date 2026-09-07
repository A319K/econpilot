from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.materials.cover_letter import generate_cover_letter
from app.materials.keywords import extract_keywords
from app.materials.regions import parse_regions
from app.materials.selection import select_resume
from app.materials.tailoring import tailor_resume
from app.models.application import Application, ApplicationStatus
from app.models.job import Job
from app.models.resume_version import ResumeVersion
from app.tracking.state_machine import transition


class PrepareError(Exception):
    """Raised when materials cannot be prepared (e.g. job not found)."""


class PrepareReport(BaseModel):
    resume_used: int
    tailored: bool = False
    regions_changed: list[str] = []
    cover_letter_id: int | None = None
    pdf_paths: dict[str, str] = {}
    llm_calls_made: int = 0


def _get_or_create_application(db: Session, job_id: int) -> Application:
    application = db.query(Application).filter(Application.job_id == job_id).one_or_none()
    if application is None:
        application = Application(job_id=job_id)
        db.add(application)
        db.flush()
    return application


def _candidate_count_for_selection(db: Session, job: Job) -> int:
    candidates = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.is_base_template.is_(True), ResumeVersion.job_family == job.job_family)
        .count()
    )
    if candidates:
        return candidates
    return db.query(ResumeVersion).filter(ResumeVersion.is_base_template.is_(True)).count()


async def prepare_materials(
    db: Session, job_id: int, tailor: bool | None = None, cover_letter: bool = True
) -> PrepareReport:
    job = db.get(Job, job_id)
    if job is None:
        raise PrepareError(f"Job {job_id} not found")

    # tailor=None means "use the configured default" (select-only unless the
    # deployment opts back into per-job tailoring).
    effective_tailor = get_settings().prepare_tailor_default if tailor is None else tailor

    application = _get_or_create_application(db, job_id)
    llm_calls_made = 0

    keywords_already_cached = job.jd_keywords is not None
    has_description = bool(job.description and job.description.strip())
    keywords = await extract_keywords(db, job)
    if not keywords_already_cached and has_description:
        llm_calls_made += 1

    candidate_count = _candidate_count_for_selection(db, job)
    base_resume = await select_resume(db, job, keywords)
    if candidate_count > 1:
        llm_calls_made += 1

    resume_used = base_resume
    tailored_flag = False
    regions_changed: list[str] = []

    if effective_tailor:
        base_regions = parse_regions(base_resume.latex_source)
        llm_calls_made += len(base_regions)

        tailored_resume = await tailor_resume(db, base_resume, job, keywords)
        if tailored_resume.id != base_resume.id:
            tailored_flag = True
            resume_used = tailored_resume
            tailored_regions = parse_regions(tailored_resume.latex_source)
            regions_changed = [
                name for name, content in base_regions.items() if tailored_regions.get(name) != content
            ]

    application.resume_version_id = resume_used.id

    pdf_paths: dict[str, str] = {}
    if resume_used.pdf_path:
        pdf_paths["resume"] = resume_used.pdf_path

    cover_letter_id = None
    if cover_letter:
        llm_calls_made += 1
        cl = await generate_cover_letter(db, application, job, keywords)
        application.cover_letter_id = cl.id
        cover_letter_id = cl.id
        if cl.pdf_path:
            pdf_paths["cover_letter"] = cl.pdf_path

    # discovered -> in_progress isn't a direct transition in the state
    # machine, so route through queued first (recorded as two history
    # entries) rather than bypassing validation with force=True.
    if application.status == ApplicationStatus.discovered:
        transition(application, ApplicationStatus.queued, note="materials prepared")
        transition(application, ApplicationStatus.in_progress, note="materials prepared")
    elif application.status == ApplicationStatus.queued:
        transition(application, ApplicationStatus.in_progress, note="materials prepared")

    db.commit()

    return PrepareReport(
        resume_used=resume_used.id,
        tailored=tailored_flag,
        regions_changed=regions_changed,
        cover_letter_id=cover_letter_id,
        pdf_paths=pdf_paths,
        llm_calls_made=llm_calls_made,
    )
