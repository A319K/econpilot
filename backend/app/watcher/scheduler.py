import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.discovery.seasonality import (
    activate_expected_companies,
    refresh_expected_months,
)
from app.discovery.watch import run_watch_scan
from app.models.queued_notification import QueuedNotification
from app.notify.factory import get_notifier

logger = logging.getLogger(__name__)

_WATCH_JOB_ID = "watch_cycle"
_SEASONAL_JOB_ID = "seasonal_preactivation"


class WatchCycleAlreadyRunning(Exception):
    """Raised by run_cycle when a cycle is already in progress."""


class CycleSummary(BaseModel):
    started: datetime
    finished: datetime | None = None
    companies: int = 0
    new_jobs: int = 0
    deactivated: int = 0
    notified: int = 0
    errors: list[str] = []


class WatcherStatus(BaseModel):
    enabled: bool
    running: bool
    last_cycle: CycleSummary | None = None
    next_run_at: datetime | None = None


def _parse_quiet_hours(quiet_hours: str | None) -> tuple[int, int] | None:
    if not quiet_hours:
        return None
    try:
        start_str, end_str = quiet_hours.split("-", 1)
        start, end = int(start_str), int(end_str)
    except ValueError:
        logger.error("invalid WATCH_QUIET_HOURS %r; ignoring", quiet_hours)
        return None
    if not (0 <= start <= 23 and 0 <= end <= 23):
        logger.error("invalid WATCH_QUIET_HOURS %r; ignoring", quiet_hours)
        return None
    return start, end


def is_quiet_hours(now: datetime | None = None) -> bool:
    settings = get_settings()
    window = _parse_quiet_hours(settings.watch_quiet_hours)
    if window is None:
        return False

    start, end = window
    if start == end:
        return False

    hour = (now or datetime.now()).hour
    if start < end:
        return start <= hour < end
    return hour >= start or hour < end


class WatcherService:
    """Owns the watch-cycle lifecycle: scheduling, overlap guarding, quiet-hours
    notification queueing, and last-cycle status reporting."""

    def __init__(self, session_factory=SessionLocal) -> None:
        self._session_factory = session_factory
        self._scheduler: AsyncIOScheduler | None = None
        self._running = False
        self._last_cycle: CycleSummary | None = None

    async def _flush_queued(self, db: Session) -> None:
        notifier = get_notifier()
        rows = db.query(QueuedNotification).order_by(QueuedNotification.created_at).all()
        for row in rows:
            try:
                await notifier.send(row.subject, row.body)
            except Exception:
                logger.exception("failed to flush queued notification %s", row.id)
            db.delete(row)
        if rows:
            db.commit()

    async def run_cycle(self) -> CycleSummary:
        if self._running:
            raise WatchCycleAlreadyRunning()

        self._running = True
        started = datetime.now(timezone.utc)
        db = self._session_factory()
        notifier = get_notifier()

        try:
            if not is_quiet_hours():
                await self._flush_queued(db)

            async def notify(subject: str, body: str) -> bool:
                if is_quiet_hours():
                    db.add(QueuedNotification(subject=subject, body=body))
                    db.flush()
                    return True
                try:
                    return await notifier.send(subject, body)
                except Exception:
                    logger.exception("notifier send failed")
                    return False

            report = await run_watch_scan(db, notify=notify)
            db.commit()
            summary = CycleSummary(
                started=started,
                finished=datetime.now(timezone.utc),
                companies=report.companies_scanned,
                new_jobs=report.new,
                deactivated=report.deactivated,
                notified=report.notified,
                errors=report.errors,
            )
        except Exception as exc:
            logger.exception("watch cycle failed")
            summary = CycleSummary(
                started=started,
                finished=datetime.now(timezone.utc),
                errors=[str(exc)],
            )
        finally:
            db.close()
            self._running = False

        self._last_cycle = summary
        return summary

    async def _scheduled_run(self) -> None:
        if self._running:
            logger.warning("watch cycle overlap detected; skipping scheduled run")
            return
        await self.run_cycle()

    async def run_seasonal_cycle(self) -> "CycleSummary":
        """Refresh the company corpus from the listings feed, then pre-activate
        companies expected to post next month. Safe to call on demand; also run
        monthly by the scheduler. Failures are contained and reported, never
        raised, so a bad network fetch can't kill the scheduler."""
        started = datetime.now(timezone.utc)
        db = self._session_factory()
        try:
            refresh = await refresh_expected_months(db)
            activation = activate_expected_companies(db, current_month=started.month)
            summary = CycleSummary(
                started=started,
                finished=datetime.now(timezone.utc),
                companies=refresh.companies_seen,
                new_jobs=refresh.companies_created,
                notified=activation.activated,
            )
        except Exception as exc:
            logger.exception("seasonal pre-activation failed")
            summary = CycleSummary(
                started=started,
                finished=datetime.now(timezone.utc),
                errors=[str(exc)],
            )
        finally:
            db.close()
        return summary

    def start(self) -> None:
        settings = get_settings()
        if not settings.watcher_enabled or self._scheduler is not None:
            return

        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self._scheduled_run,
            "interval",
            minutes=settings.watch_interval_minutes,
            max_instances=1,
            id=_WATCH_JOB_ID,
        )
        if settings.seasonal_preactivation_enabled:
            # 1st of every month, just after midnight: grow the corpus and flip
            # next month's expected companies into targets.
            self._scheduler.add_job(
                self.run_seasonal_cycle,
                "cron",
                day=1,
                hour=0,
                minute=5,
                max_instances=1,
                id=_SEASONAL_JOB_ID,
            )
        self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def status(self) -> WatcherStatus:
        settings = get_settings()
        next_run_at = None
        if self._scheduler is not None:
            job = self._scheduler.get_job(_WATCH_JOB_ID)
            if job is not None:
                next_run_at = job.next_run_time

        return WatcherStatus(
            enabled=settings.watcher_enabled,
            running=self._running,
            last_cycle=self._last_cycle,
            next_run_at=next_run_at,
        )


_watcher_service: WatcherService | None = None


def get_watcher_service() -> WatcherService:
    global _watcher_service
    if _watcher_service is None:
        _watcher_service = WatcherService()
    return _watcher_service
