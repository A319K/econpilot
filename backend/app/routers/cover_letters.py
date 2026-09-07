from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.materials.cover_letter import compile_cover_letter
from app.materials.latex import LatexError
from app.models.application import Application
from app.models.cover_letter import CoverLetter
from app.models.job import Job
from app.schemas.cover_letter import CoverLetterRead, CoverLetterReview, CoverLetterUpdate

router = APIRouter(prefix="/cover-letters", tags=["cover-letters"])


@router.get("/{cover_letter_id}", response_model=CoverLetterRead)
def get_cover_letter(cover_letter_id: int, db: Session = Depends(get_db)):
    cover_letter = db.get(CoverLetter, cover_letter_id)
    if cover_letter is None:
        raise HTTPException(status_code=404, detail="Cover letter not found")
    return cover_letter


@router.put("/{cover_letter_id}", response_model=CoverLetterRead)
def update_cover_letter(cover_letter_id: int, payload: CoverLetterUpdate, db: Session = Depends(get_db)):
    cover_letter = db.get(CoverLetter, cover_letter_id)
    if cover_letter is None:
        raise HTTPException(status_code=404, detail="Cover letter not found")

    application = db.get(Application, cover_letter.application_id)
    job = db.get(Job, application.job_id)
    try:
        pdf_path = compile_cover_letter(payload.content, job.company.name, job.id)
    except LatexError as exc:
        raise HTTPException(status_code=422, detail=f"LaTeX compilation failed: {exc}") from exc

    cover_letter.content = payload.content
    cover_letter.pdf_path = str(pdf_path)
    cover_letter.needs_review = True

    db.commit()
    db.refresh(cover_letter)
    return cover_letter


@router.patch("/{cover_letter_id}", response_model=CoverLetterRead)
def review_cover_letter(cover_letter_id: int, payload: CoverLetterReview, db: Session = Depends(get_db)):
    cover_letter = db.get(CoverLetter, cover_letter_id)
    if cover_letter is None:
        raise HTTPException(status_code=404, detail="Cover letter not found")

    cover_letter.needs_review = not payload.reviewed

    db.commit()
    db.refresh(cover_letter)
    return cover_letter
