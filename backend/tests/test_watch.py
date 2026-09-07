from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.discovery.scan as scan_module
from app.db import Base
from app.discovery.base import RawJob, SourceError
from app.discovery.scan import ScanReport
from app.discovery.watch import _notify_new_jobs, run_watch_scan
from app.models.company import AtsType, Company
from app.models.job import Job, JobFamily, JobSource, RoleType


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _fixed_score(value):
    def score(job, profile, company, now=None):
        return value, {}

    return score


def _mock_fetch(monkeypatch, source_cls, raw_jobs=None, error=None):
    async def fetch(self, company):
        if error:
            raise SourceError(error)
        return raw_jobs or []

    monkeypatch.setattr(source_cls, "fetch", fetch)


async def _empty(self=None, company=None):
    return []


@pytest.fixture(autouse=True)
def _stub_github_feeds(monkeypatch):
    """Watcher tests must never depend on the live tech-oriented feeds."""
    from app.discovery.sources.github_repo import GithubNewGradSource, GithubRepoSource

    monkeypatch.setattr(GithubRepoSource, "fetch", _empty)
    monkeypatch.setattr(GithubNewGradSource, "fetch", _empty)


@pytest.mark.asyncio
async def test_run_watch_scan_detects_new_vs_reseen(monkeypatch):
    from app.discovery.sources.github_repo import GithubRepoSource
    from app.discovery.sources.greenhouse import GreenhouseSource

    monkeypatch.setattr(scan_module, "score", _fixed_score(10.0))
    monkeypatch.setattr(GithubRepoSource, "fetch", _empty)

    session = _session()
    session.add(Company(name="Acme", ats_type=AtsType.greenhouse, ats_board_id="acme", is_target=True))
    session.commit()

    raw_jobs = [
        RawJob(
            title="Financial Analyst Intern",
            url="https://boards.greenhouse.io/acme/jobs/1",
            source=JobSource.greenhouse,
            company_name="Acme",
        )
    ]
    _mock_fetch(monkeypatch, GreenhouseSource, raw_jobs)

    report1 = await run_watch_scan(session)
    assert report1.new == 1

    report2 = await run_watch_scan(session)
    assert report2.new == 0
    assert report2.duplicates == 1


@pytest.mark.asyncio
async def test_deactivation_marks_vanished_ats_jobs_inactive(monkeypatch):
    from app.discovery.sources.github_repo import GithubRepoSource
    from app.discovery.sources.greenhouse import GreenhouseSource

    monkeypatch.setattr(scan_module, "score", _fixed_score(10.0))
    monkeypatch.setattr(GithubRepoSource, "fetch", _empty)

    session = _session()
    session.add(Company(name="Acme", ats_type=AtsType.greenhouse, ats_board_id="acme", is_target=True))
    session.commit()

    raw_jobs = [
        RawJob(
            title="Financial Analyst Intern",
            url="https://boards.greenhouse.io/acme/jobs/1",
            source=JobSource.greenhouse,
            company_name="Acme",
        )
    ]
    _mock_fetch(monkeypatch, GreenhouseSource, raw_jobs)
    await run_watch_scan(session)

    job = session.query(Job).one()
    assert job.is_active is True

    _mock_fetch(monkeypatch, GreenhouseSource, [])
    report = await run_watch_scan(session)

    session.refresh(job)
    assert job.is_active is False
    assert report.deactivated == 1


@pytest.mark.asyncio
async def test_errored_company_is_never_deactivated(monkeypatch):
    from app.discovery.sources.github_repo import GithubRepoSource
    from app.discovery.sources.lever import LeverSource

    monkeypatch.setattr(scan_module, "score", _fixed_score(10.0))
    monkeypatch.setattr(GithubRepoSource, "fetch", _empty)

    session = _session()
    session.add(Company(name="Flaky Co", ats_type=AtsType.lever, ats_board_id="flaky", is_target=True))
    session.commit()

    raw_jobs = [
        RawJob(
            title="Financial Analyst",
            url="https://jobs.lever.co/flaky/1",
            source=JobSource.lever,
            company_name="Flaky Co",
        )
    ]
    _mock_fetch(monkeypatch, LeverSource, raw_jobs)
    await run_watch_scan(session)

    job = session.query(Job).one()
    assert job.is_active is True

    _mock_fetch(monkeypatch, LeverSource, error="503 Service Unavailable")
    report = await run_watch_scan(session)

    session.refresh(job)
    assert job.is_active is True
    assert report.deactivated == 0
    assert len(report.errors) == 1


@pytest.mark.asyncio
async def test_github_sourced_jobs_are_exempt_from_deactivation(monkeypatch):
    from app.discovery.sources.github_repo import GithubRepoSource

    monkeypatch.setattr(scan_module, "score", _fixed_score(10.0))

    session = _session()
    session.add(Company(name="New Startup", ats_type=AtsType.unknown, is_target=True))
    session.commit()

    async def fetch_present(self, company):
        return [
            RawJob(
                title="Data Analyst Intern",
                url="https://simplify.jobs/p/abc",
                source=JobSource.github_repo,
                company_name="New Startup",
            )
        ]

    monkeypatch.setattr(GithubRepoSource, "fetch", fetch_present)
    await run_watch_scan(session)

    job = session.query(Job).one()
    assert job.is_active is True

    monkeypatch.setattr(GithubRepoSource, "fetch", _empty)
    report = await run_watch_scan(session)

    session.refresh(job)
    assert job.is_active is True
    assert report.deactivated == 0


def _company(session, name="Acme", **kwargs):
    company = Company(name=name, ats_type=AtsType.greenhouse, ats_board_id=name.lower(), **kwargs)
    session.add(company)
    session.commit()
    return company


def _job(session, company, title, score, source=JobSource.greenhouse):
    job = Job(
        company_id=company.id,
        title=title,
        url=f"https://example.com/{title}",
        source=source,
        role_type=RoleType.full_time,
        job_family=JobFamily.consulting,
        score=score,
        dedup_hash=title,
    )
    session.add(job)
    session.commit()
    return job


@pytest.mark.asyncio
async def test_notify_batches_and_caps_at_ten_lines_plus_more():
    session = _session()
    company = _company(session)
    jobs = [_job(session, company, f"Job {i}", score=90 - i) for i in range(12)]

    sent = {}

    async def notify(subject, body):
        sent["subject"] = subject
        sent["body"] = body
        return True

    scan = ScanReport(new_job_ids=[j.id for j in jobs])
    notified = await _notify_new_jobs(session, scan, notify)

    assert notified == 12
    assert sent["subject"] == "12 new target jobs"
    lines = sent["body"].splitlines()
    assert len(lines) == 11
    assert lines[-1] == "and 2 more"
    for job in jobs:
        session.refresh(job)
        assert job.notified_at is not None


@pytest.mark.asyncio
async def test_notify_respects_score_threshold():
    session = _session()
    company = _company(session)
    low = _job(session, company, "Low scorer", score=10)
    high = _job(session, company, "High scorer", score=80)

    async def notify(subject, body):
        return True

    scan = ScanReport(new_job_ids=[low.id, high.id])
    notified = await _notify_new_jobs(session, scan, notify)

    assert notified == 1
    session.refresh(low)
    session.refresh(high)
    assert low.notified_at is None
    assert high.notified_at is not None


@pytest.mark.asyncio
async def test_notify_never_sends_a_job_twice():
    session = _session()
    company = _company(session)
    job = _job(session, company, "Already notified", score=90)
    job.notified_at = datetime.now(timezone.utc)
    session.commit()

    calls = []

    async def notify(subject, body):
        calls.append((subject, body))
        return True

    scan = ScanReport(new_job_ids=[job.id])
    notified = await _notify_new_jobs(session, scan, notify)

    assert notified == 0
    assert calls == []


@pytest.mark.asyncio
async def test_notify_swallows_transport_failures_without_raising():
    session = _session()
    company = _company(session)
    job = _job(session, company, "Job", score=90)

    async def notify(subject, body):
        raise RuntimeError("network down")

    scan = ScanReport(new_job_ids=[job.id])
    notified = await _notify_new_jobs(session, scan, notify)

    assert notified == 1
    session.refresh(job)
    assert job.notified_at is not None
