from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.materials.latex import LatexError, build_output_name, compile_pdf
from app.materials.uploads import UploadError, safe_original_name, save_resume_pdf
from app.models.application import Application
from app.models.job import JobFamily
from app.models.resume_version import ResumeVersion
from app.schemas.resume import ResumeVersionCreate, ResumeVersionRead, ResumeVersionUpdate

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("", response_model=list[ResumeVersionRead])
def list_resumes(db: Session = Depends(get_db)):
    return db.query(ResumeVersion).order_by(ResumeVersion.id).all()


@router.get("/{resume_id}", response_model=ResumeVersionRead)
def get_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.get(ResumeVersion, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.post("", response_model=ResumeVersionRead, status_code=201)
def create_resume(payload: ResumeVersionCreate, db: Session = Depends(get_db)):
    resume = ResumeVersion(
        name=payload.name,
        job_family=payload.job_family,
        latex_source=payload.latex_source,
        keywords=payload.keywords,
        is_base_template=True,
    )
    db.add(resume)
    db.flush()

    try:
        output_name = build_output_name(payload.name, resume.id, "resume")
        resume.pdf_path = str(compile_pdf(payload.latex_source, output_name))
    except LatexError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=f"LaTeX compilation failed: {exc}") from exc

    db.commit()
    db.refresh(resume)
    return resume


@router.post("/upload", response_model=ResumeVersionRead, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    name: str = Form(...),
    job_family: JobFamily = Form(...),
    db: Session = Depends(get_db),
):
    """Register a finished PDF resume the user dragged in.

    This is the path our actual users take: they already have 2-3 resumes for
    different kinds of role and have no reason to own a LaTeX toolchain. The
    row carries no latex_source, so it is used exactly as uploaded and is never
    fed to the tailoring pipeline.
    """
    display_name = name.strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="Give this resume a name so you can tell them apart.")

    resume = ResumeVersion(
        name=display_name,
        job_family=job_family,
        latex_source=None,
        original_filename=safe_original_name(file.filename),
        keywords=[],
        is_base_template=True,
    )
    db.add(resume)
    db.flush()

    try:
        stored = await save_resume_pdf(file, display_name, resume.id)
    except UploadError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    resume.pdf_path = str(stored)
    db.commit()
    db.refresh(resume)
    return resume


@router.put("/{resume_id}", response_model=ResumeVersionRead)
def update_resume(resume_id: int, payload: ResumeVersionUpdate, db: Session = Depends(get_db)):
    resume = db.get(ResumeVersion, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    updates = payload.model_dump(exclude_unset=True)

    if resume.is_uploaded and updates.get("latex_source") is not None:
        raise HTTPException(
            status_code=422,
            detail="This resume is an uploaded PDF, so it has no LaTeX source to edit. Upload a new PDF to replace it.",
        )

    source_changed = "latex_source" in updates and updates["latex_source"] != resume.latex_source

    for field, value in updates.items():
        setattr(resume, field, value)

    if source_changed:
        try:
            output_name = build_output_name(resume.name, resume.id, "resume")
            resume.pdf_path = str(compile_pdf(resume.latex_source, output_name))
        except LatexError as exc:
            db.rollback()
            raise HTTPException(status_code=422, detail=f"LaTeX compilation failed: {exc}") from exc

    db.commit()
    db.refresh(resume)
    return resume


@router.delete("/{resume_id}", status_code=204)
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.get(ResumeVersion, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    in_use = db.query(Application).filter(Application.resume_version_id == resume_id).first()
    if in_use is not None:
        raise HTTPException(status_code=409, detail="Resume is referenced by an Application and cannot be deleted")

    db.delete(resume)
    db.commit()
