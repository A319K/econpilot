from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.mixins import TimestampMixin


class QueuedNotification(Base, TimestampMixin):
    """A notification held back during quiet hours, flushed once they end.

    Persisted (rather than kept in memory) so a process restart during quiet
    hours doesn't silently drop it.
    """

    __tablename__ = "queued_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
