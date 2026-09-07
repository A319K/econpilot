from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.answer_bank import normalize_question
from app.db import get_db
from app.models.answer_bank import AnswerBankEntry, AnswerSource
from app.schemas.answer_bank import AnswerBankCreate, AnswerBankRead, AnswerBankUpdate

router = APIRouter(tags=["answer-bank"])


@router.get("/answer-bank", response_model=list[AnswerBankRead])
def list_answers(
    approved: bool | None = None,
    source: AnswerSource | None = None,
    db: Session = Depends(get_db),
):
    """List saved answers. Filter by `approved` (e.g. approved=false to review
    pending LLM suggestions) and/or `source`."""
    query = db.query(AnswerBankEntry)
    if approved is not None:
        query = query.filter(AnswerBankEntry.approved.is_(approved))
    if source is not None:
        query = query.filter(AnswerBankEntry.source == source)
    # Pending suggestions first, then most-recently updated.
    query = query.order_by(AnswerBankEntry.approved.asc(), AnswerBankEntry.updated_at.desc())
    return query.all()


@router.post("/answer-bank", response_model=AnswerBankRead, status_code=201)
def create_answer(payload: AnswerBankCreate, db: Session = Depends(get_db)):
    """Add a human-authored answer (trusted/approved by default)."""
    qn = normalize_question(payload.question)
    if not qn:
        raise HTTPException(status_code=422, detail="question must contain letters or digits")
    if not payload.answer.strip():
        raise HTTPException(status_code=422, detail="answer must not be empty")

    entry = AnswerBankEntry(
        question_norm=qn,
        question_raw=payload.question,
        answer=payload.answer,
        source=AnswerSource.user,
        approved=payload.approved,
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="an answer for this question already exists") from exc
    db.refresh(entry)
    return entry


@router.patch("/answer-bank/{entry_id}", response_model=AnswerBankRead)
def update_answer(entry_id: int, payload: AnswerBankUpdate, db: Session = Depends(get_db)):
    """Edit an answer and/or approve it (promoting a pending LLM suggestion)."""
    entry = db.get(AnswerBankEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Answer not found")
    if payload.answer is not None:
        if not payload.answer.strip():
            raise HTTPException(status_code=422, detail="answer must not be empty")
        entry.answer = payload.answer
    if payload.approved is not None:
        entry.approved = payload.approved
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/answer-bank/{entry_id}", status_code=204)
def delete_answer(entry_id: int, db: Session = Depends(get_db)):
    entry = db.get(AnswerBankEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Answer not found")
    db.delete(entry)
    db.commit()
