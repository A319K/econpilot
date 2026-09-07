from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.answer_bank import AnswerSource


class AnswerBankRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_norm: str
    question_raw: str
    answer: str
    source: AnswerSource
    approved: bool
    times_used: int
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AnswerBankCreate(BaseModel):
    # Human-authored answers are trusted: created approved by default.
    question: str
    answer: str
    approved: bool = True


class AnswerBankUpdate(BaseModel):
    answer: str | None = None
    approved: bool | None = None
