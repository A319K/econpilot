"""Read-only endpoints added solely to support the Phase 4 frontend, per its
spec's one permitted backend exception. JobRead intentionally omits
Job.jd_keywords (it's an internal materials-pipeline cache field), but the
application detail view needs to show extracted JD keywords as tags."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.job import Job

router = APIRouter(prefix="/frontend-support", tags=["frontend-support"])


class JobKeywordsRead(BaseModel):
    jd_keywords: dict | None


@router.get("/jobs/{job_id}/keywords", response_model=JobKeywordsRead)
def get_job_keywords(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobKeywordsRead(jd_keywords=job.jd_keywords)
