import re
from datetime import datetime, timezone

from app.config import get_settings
from app.models.company import Company
from app.models.job import Job
from app.profile import Profile

SKILL_POINTS_PER_MATCH = 5
SKILL_CAP = 25

COURSEWORK_POINTS_PER_MATCH = 5
COURSEWORK_CAP = 10

EXPERIENCE_POINTS_PER_MATCH = 5
EXPERIENCE_CAP = 10

RECENCY_24H = 25
RECENCY_72H = 18
RECENCY_7D = 10
RECENCY_UNKNOWN = 5
RECENCY_STALE = 0

TARGET_COMPANY_POINTS = 15
FAMILY_MATCH_POINTS = 15

# The profile editor does not have a dedicated coursework field yet. These
# signals can still be supplied honestly through a major, skill, project, or
# experience bullet and are only rewarded when the posting asks for the same
# background.
COURSEWORK_SIGNALS: dict[str, tuple[str, ...]] = {
    "econometrics": ("econometrics", "causal inference", "regression analysis"),
    "statistics": ("statistics", "statistical methods", "probability"),
    "microeconomics": ("microeconomics", "microeconomic", "micro theory"),
    "macroeconomics": ("macroeconomics", "macroeconomic", "macro theory"),
    "accounting": ("financial accounting", "managerial accounting"),
    "quantitative methods": ("calculus", "linear algebra", "quantitative methods"),
}

# Experience is evaluated against the posting's already-qualified family. This
# avoids treating a generic "analyst" or "associate" title as relevant by
# itself while still recognizing internships, RA work, clubs, and competitions.
EXPERIENCE_SIGNALS: dict[str, tuple[str, ...]] = {
    "finance": (
        "finance intern",
        "financial analyst",
        "investment banking",
        "financial modeling",
        "valuation",
        "discounted cash flow",
        "dcf",
        "equity research",
        "credit research",
        "asset management",
        "portfolio",
        "investment club",
    ),
    "consulting": (
        "consulting intern",
        "consulting analyst",
        "economic consulting",
        "management consulting",
        "strategy consulting",
        "case competition",
        "case team",
        "client engagement",
        "litigation support",
        "antitrust",
    ),
    "data_analytics": (
        "data analyst",
        "business analyst",
        "data analysis",
        "data analytics",
        "business intelligence",
        "statistical analysis",
        "predictive modeling",
        "research project",
    ),
    "corporate": (
        "strategy analyst",
        "operations analyst",
        "corporate finance",
        "corporate strategy",
        "business operations",
        "strategic planning",
        "market research",
        "leadership program",
    ),
    "policy_research": (
        "policy analyst",
        "research assistant",
        "research associate",
        "economic research",
        "policy research",
        "public policy",
        "federal reserve",
        "central bank",
        "predoc",
        "pre-doc",
    ),
}


def _profile_keywords(profile: Profile) -> list[str]:
    return [
        *profile.skills.languages,
        *profile.skills.frameworks,
        *profile.skills.tools,
    ]


def _contains_phrase(text: str, phrase: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)"
    return re.search(pattern, text.lower()) is not None


def _profile_text(profile: Profile) -> str:
    parts: list[str] = []
    for education in profile.education:
        parts.extend((education.degree, education.major))
    for experience in profile.work_experience:
        parts.extend((experience.company, experience.title, *experience.bullets))
    for project in profile.projects:
        parts.extend((project.name, project.description or "", *project.bullets))
    parts.extend(_profile_keywords(profile))
    return " ".join(parts)


def _keyword_overlap(job: Job, profile: Profile) -> tuple[float, list[str]]:
    haystack = f"{job.title} {job.description or ''}".lower()
    matched: list[str] = []
    seen: set[str] = set()

    for keyword in _profile_keywords(profile):
        normalized = keyword.strip().lower()
        if normalized and normalized not in seen and _contains_phrase(haystack, normalized):
            matched.append(keyword)
            seen.add(normalized)

    points = min(SKILL_CAP, len(matched) * SKILL_POINTS_PER_MATCH)
    return float(points), matched


def _coursework_fit(job: Job, profile: Profile) -> tuple[float, list[str]]:
    job_text = f"{job.title} {job.description or ''}"
    profile_text = _profile_text(profile)
    matched = [
        label
        for label, phrases in COURSEWORK_SIGNALS.items()
        if any(_contains_phrase(job_text, phrase) for phrase in phrases)
        and any(_contains_phrase(profile_text, phrase) for phrase in phrases)
    ]
    points = min(COURSEWORK_CAP, len(matched) * COURSEWORK_POINTS_PER_MATCH)
    return float(points), matched


def _relevant_experience(job: Job, profile: Profile) -> tuple[float, list[str]]:
    experience_text = " ".join(
        [
            *(
                f"{item.company} {item.title} {' '.join(item.bullets)}"
                for item in profile.work_experience
            ),
            *(
                f"{item.name} {item.description or ''} {' '.join(item.bullets)}"
                for item in profile.projects
            ),
        ]
    )
    matched = [
        phrase
        for phrase in EXPERIENCE_SIGNALS.get(job.job_family.value, ())
        if _contains_phrase(experience_text, phrase)
    ]
    points = min(EXPERIENCE_CAP, len(matched) * EXPERIENCE_POINTS_PER_MATCH)
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
    coursework_points, matched_coursework = _coursework_fit(job, profile)
    experience_points, matched_experience = _relevant_experience(job, profile)
    recency_points = _recency(job, now)
    target_points = _target_company(company)
    family_points = _family_match(job)

    total = (
        keyword_points
        + coursework_points
        + experience_points
        + recency_points
        + target_points
        + family_points
    )

    breakdown = {
        "keyword_overlap": keyword_points,
        "matched_keywords": matched_keywords,
        "coursework_fit": coursework_points,
        "matched_coursework": matched_coursework,
        "relevant_experience": experience_points,
        "matched_experience_signals": matched_experience,
        "recency": recency_points,
        "target_company": target_points,
        "family_match": family_points,
    }

    return total, breakdown
