from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.application import ApplicationStatus
from app.models.job import RoleType
from app.schemas.job import JobRead


class JobSummary(BaseModel):
    id: int
    title: str
    company_name: str
    url: str
    score: float
    role_type: RoleType


class ResumeVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    pdf_path: str | None


class CoverLetterSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    needs_review: bool


class ApplicationListItem(BaseModel):
    id: int
    job_id: int
    status: ApplicationStatus
    resume_version_id: int | None
    cover_letter_id: int | None
    submitted_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    job: JobSummary


class ApplicationDetail(BaseModel):
    id: int
    job_id: int
    status: ApplicationStatus
    submitted_at: datetime | None
    notes: str | None
    status_history: list[dict] | None
    created_at: datetime
    updated_at: datetime
    job: JobRead
    resume_version: ResumeVersionSummary | None
    cover_letter: CoverLetterSummary | None


class StatusUpdate(BaseModel):
    status: ApplicationStatus
    note: str | None = None
    force: bool = False


class NotesUpdate(BaseModel):
    notes: str | None = None
