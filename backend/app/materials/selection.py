from sqlalchemy.orm import Session

from app.llm.client import complete_json
from app.materials.prompts import (
    RESUME_SELECTION_SCHEMA_HINT,
    RESUME_SELECTION_SYSTEM,
    resume_selection_user,
)
from app.models.job import Job
from app.models.resume_version import ResumeVersion


class SelectionError(Exception):
    """Raised when no base resume templates exist to select from."""


def _flatten_keyword_terms(keywords: dict) -> set[str]:
    terms: set[str] = set()
    for value in keywords.values():
        if isinstance(value, list):
            terms.update(str(v).lower() for v in value)
    return terms


def _fallback_by_overlap(candidates: list[ResumeVersion], keywords: dict) -> ResumeVersion:
    jd_terms = _flatten_keyword_terms(keywords)

    def overlap(candidate: ResumeVersion) -> int:
        candidate_terms = {str(k).lower() for k in (candidate.keywords or [])}
        return len(candidate_terms & jd_terms)

    return max(candidates, key=lambda c: (overlap(c), -c.id))


async def select_resume(db: Session, job: Job, keywords: dict) -> ResumeVersion:
    candidates = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.is_base_template.is_(True), ResumeVersion.job_family == job.job_family)
        .order_by(ResumeVersion.id)
        .all()
    )
    if not candidates:
        candidates = (
            db.query(ResumeVersion)
            .filter(ResumeVersion.is_base_template.is_(True))
            .order_by(ResumeVersion.id)
            .all()
        )

    if not candidates:
        raise SelectionError("No base resume templates available to select from")

    if len(candidates) == 1:
        return candidates[0]

    candidate_dicts = [
        {"id": c.id, "name": c.name, "keywords": c.keywords or []} for c in candidates
    ]

    try:
        result = await complete_json(
            RESUME_SELECTION_SYSTEM,
            resume_selection_user(job.title, keywords, candidate_dicts),
            RESUME_SELECTION_SCHEMA_HINT,
            max_tokens=2048,
        )
        resume_id = result.get("resume_id")
        match = next((c for c in candidates if c.id == resume_id), None)
        if match is not None:
            return match
    except Exception:
        # Any LLM/parse/validation failure falls back to the deterministic
        # keyword-overlap choice rather than aborting resume selection.
        pass

    return _fallback_by_overlap(candidates, keywords)
