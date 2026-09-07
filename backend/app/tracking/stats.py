from datetime import timedelta

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationStatus
from app.models.company import Company
from app.models.job import Job, RoleType
from app.models.mixins import utcnow

SUBMITTED_PER_DAY_WINDOW_DAYS = 30
TOP_COMPANIES_LIMIT = 10


class DailyCount(BaseModel):
    date: str
    count: int


class FunnelStats(BaseModel):
    submitted: int
    oa: int
    interview: int
    offer: int
    conversion_rates: dict[str, float]


class CompanyCount(BaseModel):
    company_id: int
    company_name: str
    count: int


class RoleTypeStats(BaseModel):
    counts_by_status: dict[str, int]
    submitted_per_day: list[DailyCount]
    funnel: FunnelStats
    avg_hours_to_submit: float | None
    top_companies: list[CompanyCount]


class StatsResponse(BaseModel):
    internship: RoleTypeStats
    full_time: RoleTypeStats
    all: RoleTypeStats


def _base_query(db: Session, role_type: RoleType | None):
    query = db.query(Application).join(Job, Application.job_id == Job.id)
    if role_type is not None:
        query = query.filter(Job.role_type == role_type)
    return query


def _counts_by_status(db: Session, role_type: RoleType | None) -> dict[str, int]:
    query = db.query(Application.status, func.count(Application.id)).join(Job, Application.job_id == Job.id)
    if role_type is not None:
        query = query.filter(Job.role_type == role_type)
    query = query.group_by(Application.status)

    counts = {status.value: 0 for status in ApplicationStatus}
    for status, count in query.all():
        counts[status.value] = count
    return counts


def _submitted_per_day(db: Session, role_type: RoleType | None) -> list[DailyCount]:
    since = utcnow() - timedelta(days=SUBMITTED_PER_DAY_WINDOW_DAYS)
    day = func.date(Application.submitted_at)

    query = (
        db.query(day.label("day"), func.count(Application.id))
        .join(Job, Application.job_id == Job.id)
        .filter(Application.submitted_at.isnot(None), Application.submitted_at >= since)
    )
    if role_type is not None:
        query = query.filter(Job.role_type == role_type)
    query = query.group_by(day).order_by(day)

    return [DailyCount(date=str(d), count=c) for d, c in query.all()]


def _funnel(counts_by_status: dict[str, int]) -> FunnelStats:
    submitted = counts_by_status.get("submitted", 0)
    oa = counts_by_status.get("oa", 0)
    interview = counts_by_status.get("interview", 0)
    offer = counts_by_status.get("offer", 0)

    def rate(numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 4) if denominator else 0.0

    return FunnelStats(
        submitted=submitted,
        oa=oa,
        interview=interview,
        offer=offer,
        conversion_rates={
            "submitted_to_oa": rate(oa, submitted),
            "oa_to_interview": rate(interview, oa),
            "interview_to_offer": rate(offer, interview),
        },
    )


def _avg_hours_to_submit(db: Session, role_type: RoleType | None) -> float | None:
    hours_expr = (func.julianday(Application.submitted_at) - func.julianday(Job.discovered_at)) * 24.0

    query = (
        db.query(func.avg(hours_expr))
        .join(Job, Application.job_id == Job.id)
        .filter(Application.submitted_at.isnot(None))
    )
    if role_type is not None:
        query = query.filter(Job.role_type == role_type)

    result = query.scalar()
    return round(result, 2) if result is not None else None


def _top_companies(db: Session, role_type: RoleType | None) -> list[CompanyCount]:
    query = (
        db.query(Company.id, Company.name, func.count(Application.id).label("app_count"))
        .join(Job, Job.company_id == Company.id)
        .join(Application, Application.job_id == Job.id)
    )
    if role_type is not None:
        query = query.filter(Job.role_type == role_type)

    query = query.group_by(Company.id, Company.name).order_by(func.count(Application.id).desc()).limit(
        TOP_COMPANIES_LIMIT
    )

    return [CompanyCount(company_id=cid, company_name=name, count=count) for cid, name, count in query.all()]


def _role_type_stats(db: Session, role_type: RoleType | None) -> RoleTypeStats:
    counts_by_status = _counts_by_status(db, role_type)
    return RoleTypeStats(
        counts_by_status=counts_by_status,
        submitted_per_day=_submitted_per_day(db, role_type),
        funnel=_funnel(counts_by_status),
        avg_hours_to_submit=_avg_hours_to_submit(db, role_type),
        top_companies=_top_companies(db, role_type),
    )


def compute_stats(db: Session) -> StatsResponse:
    return StatsResponse(
        internship=_role_type_stats(db, RoleType.internship),
        full_time=_role_type_stats(db, RoleType.full_time),
        all=_role_type_stats(db, None),
    )
