from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.job import JobFamily


class ResumeVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    job_family: JobFamily
    latex_source: str
    pdf_path: str | None
    is_base_template: bool
    parent_id: int | None
    keywords: list | None
    created_at: datetime
    updated_at: datetime


class ResumeVersionCreate(BaseModel):
    name: str
    job_family: JobFamily
    latex_source: str
    keywords: list[str] = []


class ResumeVersionUpdate(BaseModel):
    name: str | None = None
    job_family: JobFamily | None = None
    latex_source: str | None = None
    keywords: list[str] | None = None
