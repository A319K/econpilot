import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin, utcnow


class JobSource(str, enum.Enum):
    greenhouse = "greenhouse"
    lever = "lever"
    ashby = "ashby"
    workday = "workday"
    usajobs = "usajobs"
    github_repo = "github_repo"
    github_newgrad = "github_newgrad"
    manual = "manual"


class RoleType(str, enum.Enum):
    internship = "internship"
    full_time = "full_time"


class JobFamily(str, enum.Enum):
    finance = "finance"
    consulting = "consulting"
    data_analytics = "data_analytics"
    corporate = "corporate"
    policy_research = "policy_research"
    other = "other"


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    source: Mapped[JobSource] = mapped_column(Enum(JobSource, native_enum=False), nullable=False)
    role_type: Mapped[RoleType] = mapped_column(Enum(RoleType, native_enum=False), nullable=False)
    job_family: Mapped[JobFamily] = mapped_column(
        Enum(JobFamily, native_enum=False), nullable=False, default=JobFamily.other
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_breakdown: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dedup_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    jd_keywords: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    company: Mapped["Company"] = relationship(back_populates="jobs")
    applications: Mapped[list["Application"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
