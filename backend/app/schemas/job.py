from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.job import JobFamily, JobSource, RoleType


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    title: str
    location: str | None
    url: str
    source: JobSource
    role_type: RoleType
    job_family: JobFamily
    description: str | None
    posted_at: datetime | None
    discovered_at: datetime
    score: float
    score_breakdown: dict | None
    is_active: bool
    dedup_hash: str
    created_at: datetime
    updated_at: datetime


class ManualJobCreate(BaseModel):
    url: str
    title: str | None = None
    company_name: str | None = None
    role_type: RoleType
    notes: str | None = None
