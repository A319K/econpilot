import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base
from app.models.queued_notification import QueuedNotification
from app.watcher import scheduler as scheduler_module
from app.watcher.scheduler import WatcherService, WatchCycleAlreadyRunning, is_quiet_hours


def _session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.mark.asyncio
async def test_run_cycle_reports_summary(monkeypatch):
    async def fake_run_watch_scan(db, notify=None):
        from app.discovery.watch import WatchReport

        return WatchReport(companies_scanned=2, jobs_found=3, new=1, duplicates=2, deactivated=0, notified=1)

    monkeypatch.setattr(scheduler_module, "run_watch_scan", fake_run_watch_scan)
    monkeypatch.setattr(scheduler_module, "is_quiet_hours", lambda now=None: False)

    service = WatcherService(session_factory=_session_factory())
    summary = await service.run_cycle()

    assert summary.companies == 2
    assert summary.new_jobs == 1
    assert summary.notified == 1
    assert service.status.last_cycle == summary
    assert service.running is False


@pytest.mark.asyncio
async def test_overlap_guard_rejects_concurrent_run_cycle(monkeypatch):
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_run_watch_scan(db, notify=None):
        from app.discovery.watch import WatchReport

        started.set()
        await release.wait()
        return WatchReport()

    monkeypatch.setattr(scheduler_module, "run_watch_scan", fake_run_watch_scan)
    monkeypatch.setattr(scheduler_module, "is_quiet_hours", lambda now=None: False)

    service = WatcherService(session_factory=_session_factory())
    first = asyncio.create_task(service.run_cycle())
    await started.wait()

    with pytest.raises(WatchCycleAlreadyRunning):
        await service.run_cycle()

    release.set()
    await first


@pytest.mark.asyncio
async def test_scheduled_run_skips_when_already_running(monkeypatch, caplog):
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_run_watch_scan(db, notify=None):
        from app.discovery.watch import WatchReport

        started.set()
        await release.wait()
        return WatchReport()

    monkeypatch.setattr(scheduler_module, "run_watch_scan", fake_run_watch_scan)
    monkeypatch.setattr(scheduler_module, "is_quiet_hours", lambda now=None: False)

    service = WatcherService(session_factory=_session_factory())
    first = asyncio.create_task(service._scheduled_run())
    await started.wait()

    # A second scheduled fire while the first is still running must be a no-op,
    # not raise, and not start a second scan.
    await service._scheduled_run()

    release.set()
    await first


def test_is_quiet_hours_handles_wraparound(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("WATCH_QUIET_HOURS", "23-07")

    assert is_quiet_hours(datetime(2026, 1, 1, 23, 30)) is True
    assert is_quiet_hours(datetime(2026, 1, 1, 3, 0)) is True
    assert is_quiet_hours(datetime(2026, 1, 1, 12, 0)) is False
    get_settings.cache_clear()


def test_is_quiet_hours_disabled_by_default(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("WATCH_QUIET_HOURS", raising=False)
    assert is_quiet_hours(datetime(2026, 1, 1, 23, 30)) is False
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_quiet_hours_queues_notification_instead_of_sending(monkeypatch):
    async def fake_run_watch_scan(db, notify):
        # Simulate watch.py finding one notify-worthy new job.
        await notify("1 new target jobs", "90 | Acme | SWE Intern | https://x")
        from app.discovery.watch import WatchReport

        return WatchReport(notified=1)

    sent = []

    class FakeNotifier:
        name = "none"

        async def send(self, subject, body):
            sent.append((subject, body))
            return True

    monkeypatch.setattr(scheduler_module, "run_watch_scan", fake_run_watch_scan)
    monkeypatch.setattr(scheduler_module, "is_quiet_hours", lambda now=None: True)
    monkeypatch.setattr(scheduler_module, "get_notifier", lambda: FakeNotifier())

    session_factory = _session_factory()
    service = WatcherService(session_factory=session_factory)
    await service.run_cycle()

    db = session_factory()
    queued = db.query(QueuedNotification).all()
    assert len(queued) == 1
    assert queued[0].subject == "1 new target jobs"
    assert sent == []
    db.close()


@pytest.mark.asyncio
async def test_flush_queued_sends_and_clears_after_quiet_hours_end(monkeypatch):
    async def fake_run_watch_scan(db, notify):
        from app.discovery.watch import WatchReport

        return WatchReport()

    sent = []

    class FakeNotifier:
        name = "none"

        async def send(self, subject, body):
            sent.append((subject, body))
            return True

    monkeypatch.setattr(scheduler_module, "run_watch_scan", fake_run_watch_scan)
    monkeypatch.setattr(scheduler_module, "is_quiet_hours", lambda now=None: False)
    monkeypatch.setattr(scheduler_module, "get_notifier", lambda: FakeNotifier())

    session_factory = _session_factory()
    db = session_factory()
    db.add(QueuedNotification(subject="queued earlier", body="body"))
    db.commit()
    db.close()

    service = WatcherService(session_factory=session_factory)
    await service.run_cycle()

    assert sent == [("queued earlier", "body")]

    db = session_factory()
    assert db.query(QueuedNotification).count() == 0
    db.close()


@pytest.mark.asyncio
async def test_run_seasonal_cycle_refreshes_and_activates(monkeypatch):
    from app.discovery.seasonality import PreActivation, SeasonalityRefresh

    async def fake_refresh(db):
        return SeasonalityRefresh(companies_seen=50, companies_created=12)

    def fake_activate(db, current_month):
        return PreActivation(target_month=(current_month % 12) + 1, activated=7)

    monkeypatch.setattr(scheduler_module, "refresh_expected_months", fake_refresh)
    monkeypatch.setattr(scheduler_module, "activate_expected_companies", fake_activate)

    service = WatcherService(session_factory=_session_factory())
    summary = await service.run_seasonal_cycle()

    assert summary.errors == []
    assert summary.companies == 50  # seen
    assert summary.new_jobs == 12  # created
    assert summary.notified == 7  # activated


@pytest.mark.asyncio
async def test_run_seasonal_cycle_contains_failures(monkeypatch):
    async def boom(db):
        raise RuntimeError("network down")

    monkeypatch.setattr(scheduler_module, "refresh_expected_months", boom)

    service = WatcherService(session_factory=_session_factory())
    summary = await service.run_seasonal_cycle()

    assert summary.errors == ["network down"]


@pytest.mark.asyncio
async def test_seasonal_job_registered_when_enabled(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "watcher_enabled", True, raising=False)
    monkeypatch.setattr(settings, "seasonal_preactivation_enabled", True, raising=False)
    monkeypatch.setattr(scheduler_module, "get_settings", lambda: settings)

    service = WatcherService(session_factory=_session_factory())
    try:
        service.start()
        assert service._scheduler.get_job("seasonal_preactivation") is not None
        assert service._scheduler.get_job("watch_cycle") is not None
    finally:
        service.stop()


@pytest.mark.asyncio
async def test_seasonal_job_not_registered_when_disabled(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "watcher_enabled", True, raising=False)
    monkeypatch.setattr(settings, "seasonal_preactivation_enabled", False, raising=False)
    monkeypatch.setattr(scheduler_module, "get_settings", lambda: settings)

    service = WatcherService(session_factory=_session_factory())
    try:
        service.start()
        assert service._scheduler.get_job("seasonal_preactivation") is None
        assert service._scheduler.get_job("watch_cycle") is not None
    finally:
        service.stop()
