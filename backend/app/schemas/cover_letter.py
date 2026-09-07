from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CoverLetterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    content: str
    pdf_path: str | None
    needs_review: bool
    created_at: datetime
    updated_at: datetime


class CoverLetterUpdate(BaseModel):
    content: str


class CoverLetterReview(BaseModel):
    reviewed: bool
