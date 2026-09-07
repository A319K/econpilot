import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin


class AtsType(str, enum.Enum):
    greenhouse = "greenhouse"
    lever = "lever"
    ashby = "ashby"
    workday = "workday"
    other = "other"
    unknown = "unknown"


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    careers_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    ats_type: Mapped[AtsType] = mapped_column(
        Enum(AtsType, native_enum=False), nullable=False, default=AtsType.unknown
    )
    ats_board_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Last time the active resolver probed this company against the job-board
    # APIs (only set for companies that were unknown when probed). Lets scans
    # skip re-probing companies already checked. None = never actively probed.
    ats_probed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_target: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Months (1-12) this company has historically opened internships, derived
    # from prior-season listings. Drives the 1st-of-month pre-activation cron
    # (Phase B): companies expected next month are flipped to is_target.
    expected_months: Mapped[list | None] = mapped_column(JSON, nullable=True)

    jobs: Mapped[list["Job"]] = relationship(back_populates="company", cascade="all, delete-orphan")
