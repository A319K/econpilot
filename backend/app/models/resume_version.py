from sqlalchemy import Boolean, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.job import JobFamily
from app.models.mixins import TimestampMixin
from sqlalchemy import Enum


class ResumeVersion(Base, TimestampMixin):
    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_family: Mapped[JobFamily] = mapped_column(Enum(JobFamily, native_enum=False), nullable=False)
    # Null for resumes the user uploaded as a finished PDF - there is no
    # source document to compile or tailor in that case.
    latex_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_base_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("resume_versions.id"), nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSON, nullable=True)

    parent: Mapped["ResumeVersion | None"] = relationship(remote_side=[id])

    @property
    def is_uploaded(self) -> bool:
        """True when this is a PDF the user supplied rather than a template we
        compile. Such resumes are used as-is and can't be LLM-tailored."""
        return self.latex_source is None
