import re
from datetime import datetime, timezone

from app.config import get_settings
from app.models.company import Company
from app.models.job import Job
from app.profile import Profile

KEYWORD_POINTS_PER_MATCH = 5
KEYWORD_CAP = 40

RECENCY_24H = 30
RECENCY_72H = 20
RECENCY_7D = 10
RECENCY_UNKNOWN = 5
RECENCY_STALE = 0

TARGET_COMPANY_POINTS = 20
FAMILY_MATCH_POINTS = 10


def _profile_keywords(profile: Profile) -> list[str]:
    return [
        *profile.skills.languages,
        *profile.skills.frameworks,
        *profile.skills.tools,
    ]


def _keyword_overlap(job: Job, profile: Profile) -> tuple[float, list[str]]:
    haystack = f"{job.title} {job.description or ''}".lower()
    matched: list[str] = []

    for keyword in _profile_keywords(profile):
        pattern = r"\b" + re.escape(keyword.lower()) + r"\b"
        if re.search(pattern, haystack):
            matched.append(keyword)

    points = min(KEYWORD_CAP, len(matched) * KEYWORD_POINTS_PER_MATCH)
    return float(points), matched


def _recency(job: Job, now: datetime) -> float:
    if job.posted_at is None:
        return float(RECENCY_UNKNOWN)

    posted_at = job.posted_at
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)

    age = now - posted_at
    hours = age.total_seconds() / 3600

    if hours <= 24:
        return float(RECENCY_24H)
    if hours <= 72:
        return float(RECENCY_72H)
    if hours <= 24 * 7:
        return float(RECENCY_7D)
    return float(RECENCY_STALE)


def _target_company(company: Company) -> float:
    return float(TARGET_COMPANY_POINTS) if company.is_target else 0.0


def _family_match(job: Job) -> float:
    settings = get_settings()
    return float(FAMILY_MATCH_POINTS) if job.job_family.value in settings.preferred_job_families else 0.0


def score(
    job: Job, profile: Profile, company: Company, now: datetime | None = None
) -> tuple[float, dict]:
    now = now or datetime.now(timezone.utc)

    keyword_points, matched_keywords = _keyword_overlap(job, profile)
    recency_points = _recency(job, now)
    target_points = _target_company(company)
    family_points = _family_match(job)

    total = keyword_points + recency_points + target_points + family_points

    breakdown = {
        "keyword_overlap": keyword_points,
        "matched_keywords": matched_keywords,
        "recency": recency_points,
        "target_company": target_points,
        "family_match": family_points,
    }

    return total, breakdown
