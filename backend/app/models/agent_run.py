import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.mixins import TimestampMixin, utcnow


class AgentRunStatus(str, enum.Enum):
    running = "running"
    paused = "paused"
    ready_for_review = "ready_for_review"
    failed = "failed"
    abandoned = "abandoned"


class PauseReason(str, enum.Enum):
    login_required = "login_required"
    captcha = "captcha"
    unmapped_required_field = "unmapped_required_field"
    cap_exceeded = "cap_exceeded"
    error = "error"


# Statuses in which a run is holding the shared browser and can still be
# resumed by the human. Used for the global single-active-run guard.
ACTIVE_STATUSES = {AgentRunStatus.running, AgentRunStatus.paused}


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False)
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus, native_enum=False), nullable=False, default=AgentRunStatus.running
    )
    pause_reason: Mapped[PauseReason | None] = mapped_column(
        Enum(PauseReason, native_enum=False), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Every action + its result, appended in order (see app.agent.loop).
    action_log: Mapped[list | None] = mapped_column(JSON, nullable=True)
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    screenshots_dir: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    application: Mapped["Application"] = relationship()
