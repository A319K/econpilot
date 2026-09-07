from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.materials.latex import LatexError, build_output_name, compile_pdf
from app.models.application import Application
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


@router.put("/{resume_id}", response_model=ResumeVersionRead)
def update_resume(resume_id: int, payload: ResumeVersionUpdate, db: Session = Depends(get_db)):
    resume = db.get(ResumeVersion, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    updates = payload.model_dump(exclude_unset=True)
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
