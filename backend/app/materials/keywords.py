from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm.client import complete_json
from app.materials.prompts import (
    KEYWORD_EXTRACTION_SCHEMA_HINT,
    KEYWORD_EXTRACTION_SYSTEM,
    keyword_extraction_user,
)
from app.models.job import Job

EMPTY_KEYWORDS = {"skills": [], "responsibilities": [], "qualifications": [], "nice_to_have": []}
_REQUIRED_KEYS = tuple(EMPTY_KEYWORDS.keys())


def _normalize(raw: dict) -> dict:
    normalized = {}
    for key in _REQUIRED_KEYS:
        value = raw.get(key)
        normalized[key] = value if isinstance(value, list) else []
    return normalized


async def extract_keywords(db: Session, job: Job) -> dict:
    """Extract JD keywords for a job, caching the result on job.jd_keywords.

    Returns the cached value without an LLM call if already computed, and
    without an LLM call at all if the job has no description.
    """
    if job.jd_keywords is not None:
        return job.jd_keywords

    if not job.description or not job.description.strip():
        job.jd_keywords = dict(EMPTY_KEYWORDS)
        db.flush()
        return job.jd_keywords

    settings = get_settings()
    truncated = job.description[: settings.jd_description_max_chars]

    raw = await complete_json(
        KEYWORD_EXTRACTION_SYSTEM,
        keyword_extraction_user(job.title, truncated),
        KEYWORD_EXTRACTION_SCHEMA_HINT,
        max_tokens=2048,
    )

    job.jd_keywords = _normalize(raw)
    db.flush()
    return job.jd_keywords
