import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin


class ApplicationStatus(str, enum.Enum):
    discovered = "discovered"
    queued = "queued"
    in_progress = "in_progress"
    ready_to_submit = "ready_to_submit"
    submitted = "submitted"
    oa = "oa"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"
    withdrawn = "withdrawn"


class Application(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False)
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, native_enum=False), nullable=False, default=ApplicationStatus.discovered
    )
    resume_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("resume_versions.id"), nullable=True
    )
    cover_letter_id: Mapped[int | None] = mapped_column(ForeignKey("cover_letters.id"), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_history: Mapped[list | None] = mapped_column(JSON, nullable=True)

    job: Mapped["Job"] = relationship(back_populates="applications")
    resume_version: Mapped["ResumeVersion | None"] = relationship(foreign_keys=[resume_version_id])
    cover_letter: Mapped["CoverLetter | None"] = relationship(
        foreign_keys=[cover_letter_id], post_update=True
    )
