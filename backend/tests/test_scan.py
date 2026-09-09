import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.discovery.base import RawJob, SourceError
from app.discovery.scan import run_scan
from app.models.company import AtsType, Company
from app.models.job import Job, JobSource, RoleType


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _mock_fetch(monkeypatch, source_cls, raw_jobs=None, error=None):
    async def fetch(self, company):
        if error:
            raise SourceError(error)
        return raw_jobs or []

    monkeypatch.setattr(source_cls, "fetch", fetch)


@pytest.fixture(autouse=True)
def _stub_newgrad_source(monkeypatch):
    """The new-grad source fetches a live GitHub feed. Stub it empty by default
    so scans in these tests stay hermetic; tests exercising it override this."""
    from app.discovery.sources.github_repo import GithubNewGradSource

    _mock_fetch(monkeypatch, GithubNewGradSource, [])


@pytest.mark.asyncio
async def test_run_scan_skips_companies_without_known_ats_type(monkeypatch):
    from app.discovery.sources.greenhouse import GreenhouseSource
    from app.discovery.sources.github_repo import GithubRepoSource

    session = _session()
    session.add(Company(name="Unknown Co", ats_type=AtsType.unknown))
    session.add(Company(name="Custom Site", ats_type=AtsType.other))
    session.commit()

    _mock_fetch(monkeypatch, GreenhouseSource, [])
    monkeypatch.setattr(GithubRepoSource, "fetch", lambda self, company: _empty())

    report = await run_scan(session)
    assert report.companies_scanned == 0


async def _empty():
    return []


@pytest.mark.asyncio
async def test_run_scan_ingests_jobs_from_ats_source(monkeypatch):
    from app.discovery.sources.greenhouse import GreenhouseSource
    from app.discovery.sources.github_repo import GithubRepoSource

    session = _session()
    company = Company(name="Acme", ats_type=AtsType.greenhouse, ats_board_id="acme")
    session.add(company)
    session.commit()

    raw_jobs = [
        RawJob(
            title="Financial Analyst Intern",
            url="https://boards.greenhouse.io/acme/jobs/1",
            location="Remote",
            source=JobSource.greenhouse,
            company_name="Acme",
        )
    ]
    _mock_fetch(monkeypatch, GreenhouseSource, raw_jobs)
    monkeypatch.setattr(GithubRepoSource, "fetch", lambda self, company: _empty())

    report = await run_scan(session)

    assert report.companies_scanned == 1
    assert report.jobs_found == 1
    assert report.new == 1
    assert report.duplicates == 0
    assert session.query(Job).count() == 1


@pytest.mark.asyncio
async def test_run_scan_records_source_errors_without_aborting(monkeypatch):
    from app.discovery.sources.greenhouse import GreenhouseSource
    from app.discovery.sources.lever import LeverSource
    from app.discovery.sources.github_repo import GithubRepoSource

    session = _session()
    session.add(Company(name="Broken Co", ats_type=AtsType.greenhouse, ats_board_id="broken"))
    session.add(Company(name="Good Co", ats_type=AtsType.lever, ats_board_id="good"))
    session.commit()

    _mock_fetch(monkeypatch, GreenhouseSource, error="503 Service Unavailable")
    raw_jobs = [
        RawJob(
            title="Financial Analyst",
            url="https://jobs.lever.co/good/1",
            source=JobSource.lever,
            company_name="Good Co",
        )
    ]
    _mock_fetch(monkeypatch, LeverSource, raw_jobs)
    monkeypatch.setattr(GithubRepoSource, "fetch", lambda self, company: _empty())

    report = await run_scan(session)

    assert report.companies_scanned == 2
    assert len(report.errors) == 1
    assert "Broken Co" in report.errors[0]
    assert report.new == 1


@pytest.mark.asyncio
async def test_run_scan_filters_by_role_type(monkeypatch):
    from app.discovery.sources.greenhouse import GreenhouseSource
    from app.discovery.sources.github_repo import GithubRepoSource

    session = _session()
    session.add(Company(name="Acme", ats_type=AtsType.greenhouse, ats_board_id="acme"))
    session.commit()

    raw_jobs = [
        RawJob(
            title="Senior Financial Analyst",
            url="https://boards.greenhouse.io/acme/jobs/1",
            source=JobSource.greenhouse,
            company_name="Acme",
        ),
        RawJob(
            title="Financial Analyst Intern",
            url="https://boards.greenhouse.io/acme/jobs/2",
            source=JobSource.greenhouse,
            company_name="Acme",
        ),
    ]
    _mock_fetch(monkeypatch, GreenhouseSource, raw_jobs)
    monkeypatch.setattr(GithubRepoSource, "fetch", lambda self, company: _empty())

    # A full-time scan sweeps the ATS sources and keeps only full-time roles;
    # the intern posting is classified as an internship and dropped. (Internship
    # scans take a different path entirely - see the github-only test below.)
    report = await run_scan(session, role_type="full_time")

    assert report.jobs_found == 2
    assert report.new == 1
    assert session.query(Job).count() == 1
    assert session.query(Job).first().title == "Senior Financial Analyst"


@pytest.mark.asyncio
async def test_run_scan_internship_uses_ats_and_github_sources(monkeypatch):
    from app.discovery.sources.github_repo import GithubRepoSource
    from app.discovery.sources.greenhouse import GreenhouseSource

    session = _session()
    session.add(Company(name="Acme", ats_type=AtsType.greenhouse, ats_board_id="acme"))
    session.commit()

    ats_jobs = [
        RawJob(
            title="Financial Analyst Intern",
            url="https://boards.greenhouse.io/acme/jobs/1",
            source=JobSource.greenhouse,
            company_name="Acme",
        )
    ]
    _mock_fetch(monkeypatch, GreenhouseSource, ats_jobs)

    async def _github(self, company):
        return [
            RawJob(
                title="Data Analyst Intern",
                url="https://example.com/gh-intern",
                source=JobSource.github_repo,
                company_name="Acme",
            )
        ]

    monkeypatch.setattr(GithubRepoSource, "fetch", _github)

    report = await run_scan(session, role_type="internship")

    assert report.companies_scanned == 1
    assert session.query(Job).count() == 2
    assert {job.source for job in session.query(Job).all()} == {
        JobSource.greenhouse,
        JobSource.github_repo,
    }


@pytest.mark.asyncio
async def test_run_scan_newgrad_source_ingested_as_full_time(monkeypatch):
    from app.discovery.sources.github_repo import GithubNewGradSource, GithubRepoSource

    session = _session()

    async def _newgrad(self, company):
        return [
            RawJob(
                title="Financial Analyst, New Grad",
                url="https://example.com/ng-swe",
                source=JobSource.github_newgrad,
                company_name="Acme",
            )
        ]

    # Internship feed empty; the new-grad feed carries one full-time role.
    monkeypatch.setattr(GithubRepoSource, "fetch", lambda self, company: _empty())
    monkeypatch.setattr(GithubNewGradSource, "fetch", _newgrad)

    # An internship scan must NOT pull the new-grad feed...
    intern_report = await run_scan(session, role_type="internship")
    assert intern_report.new == 0
    assert session.query(Job).count() == 0

    # ...but a full-time scan does, and files it as a full-time role.
    ft_report = await run_scan(session, role_type="full_time")
    assert ft_report.new == 1
    job = session.query(Job).one()
    assert job.source == JobSource.github_newgrad
    assert job.role_type == RoleType.full_time


@pytest.mark.asyncio
async def test_run_scan_drops_unclassified_noise_for_every_role_type(monkeypatch):
    from app.discovery.sources.greenhouse import GreenhouseSource
    from app.discovery.sources.github_repo import GithubRepoSource

    session = _session()
    session.add(Company(name="Acme", ats_type=AtsType.greenhouse, ats_board_id="acme"))
    session.commit()

    raw_jobs = [
        RawJob(  # unrelated full-time role -> dropped
            title="Registered Nurse",
            url="https://boards.greenhouse.io/acme/jobs/1",
            source=JobSource.greenhouse,
            company_name="Acme",
        ),
        RawJob(  # classified econ role -> kept
            title="Senior Financial Analyst",
            url="https://boards.greenhouse.io/acme/jobs/2",
            source=JobSource.greenhouse,
            company_name="Acme",
        ),
        RawJob(  # unrelated internships are filtered too
            title="Marketing Intern",
            url="https://boards.greenhouse.io/acme/jobs/3",
            source=JobSource.greenhouse,
            company_name="Acme",
        ),
    ]
    _mock_fetch(monkeypatch, GreenhouseSource, raw_jobs)
    monkeypatch.setattr(GithubRepoSource, "fetch", lambda self, company: _empty())

    report = await run_scan(session)

    assert report.jobs_found == 3
    assert report.filtered == 2
    assert report.new == 1
    titles = {j.title for j in session.query(Job).all()}
    assert titles == {"Senior Financial Analyst"}


@pytest.mark.asyncio
async def test_run_scan_targets_only_filters_companies(monkeypatch):
    from app.discovery.sources.greenhouse import GreenhouseSource
    from app.discovery.sources.github_repo import GithubRepoSource

    session = _session()
    session.add(Company(name="Target Co", ats_type=AtsType.greenhouse, ats_board_id="t", is_target=True))
    session.add(Company(name="Other Co", ats_type=AtsType.greenhouse, ats_board_id="o", is_target=False))
    session.commit()

    _mock_fetch(monkeypatch, GreenhouseSource, [])
    monkeypatch.setattr(GithubRepoSource, "fetch", lambda self, company: _empty())

    report = await run_scan(session, targets_only=True)
    assert report.companies_scanned == 1


@pytest.mark.asyncio
async def test_run_scan_includes_github_repo_jobs(monkeypatch):
    from app.discovery.sources.github_repo import GithubRepoSource

    session = _session()

    async def fetch(self, company):
        return [
            RawJob(
                title="Data Analyst Intern",
                url="https://simplify.jobs/p/abc",
                source=JobSource.github_repo,
                company_name="New Startup",
            )
        ]

    monkeypatch.setattr(GithubRepoSource, "fetch", fetch)

    report = await run_scan(session)

    assert report.new == 1
    job = session.query(Job).one()
    assert job.company.name == "New Startup"
    assert job.company.ats_type == AtsType.unknown


@pytest.mark.asyncio
async def test_run_scan_ingests_configured_usajobs_economists(monkeypatch):
    from app.config import get_settings
    from app.discovery.sources.github_repo import GithubRepoSource
    from app.discovery.sources.usajobs import UsaJobsSource

    settings = get_settings()
    monkeypatch.setattr(settings, "usajobs_api_key", "test-key")
    monkeypatch.setattr(settings, "usajobs_user_agent", "student@example.com")
    monkeypatch.setattr(GithubRepoSource, "fetch", lambda self, company: _empty())

    async def fetch_usajobs(self, company):
        assert self.date_posted_days == settings.scan_max_age_days
        return [
            RawJob(
                title="Economist",
                url="https://www.usajobs.gov/job/810000001",
                location="Washington, District of Columbia",
                description="Analyze labor market data.",
                source=JobSource.usajobs,
                company_name="Bureau of Labor Statistics",
            )
        ]

    monkeypatch.setattr(UsaJobsSource, "fetch", fetch_usajobs)
    session = _session()

    report = await run_scan(session, role_type="full_time")

    assert report.new == 1
    job = session.query(Job).one()
    assert job.source == JobSource.usajobs
    assert job.role_type == RoleType.full_time
    assert job.url.startswith("https://www.usajobs.gov/")
    assert job.company.ats_type == AtsType.other


@pytest.mark.asyncio
async def test_successful_usajobs_snapshot_deactivates_missing_jobs(monkeypatch):
    from app.config import get_settings
    from app.discovery.sources.github_repo import GithubRepoSource
    from app.discovery.sources.usajobs import UsaJobsSource
    from app.discovery.pipeline import ingest_raw_job

    settings = get_settings()
    monkeypatch.setattr(settings, "usajobs_api_key", "test-key")
    monkeypatch.setattr(settings, "usajobs_user_agent", "student@example.com")
    monkeypatch.setattr(GithubRepoSource, "fetch", lambda self, company: _empty())
    monkeypatch.setattr(UsaJobsSource, "fetch", lambda self, company: _empty())
    session = _session()
    old, _ = ingest_raw_job(
        session,
        RawJob(
            title="Economist",
            url="https://www.usajobs.gov/job/old",
            source=JobSource.usajobs,
            company_name="Bureau of Labor Statistics",
        ),
    )
    session.commit()

    await run_scan(session, role_type="full_time")

    assert old.is_active is False


@pytest.mark.asyncio
async def test_usajobs_error_never_deactivates_existing_jobs(monkeypatch):
    from app.config import get_settings
    from app.discovery.pipeline import ingest_raw_job
    from app.discovery.sources.github_repo import GithubRepoSource
    from app.discovery.sources.usajobs import UsaJobsSource

    settings = get_settings()
    monkeypatch.setattr(settings, "usajobs_api_key", "test-key")
    monkeypatch.setattr(settings, "usajobs_user_agent", "student@example.com")
    monkeypatch.setattr(GithubRepoSource, "fetch", lambda self, company: _empty())

    async def fail(self, company):
        raise SourceError("temporarily unavailable")

    monkeypatch.setattr(UsaJobsSource, "fetch", fail)
    session = _session()
    old, _ = ingest_raw_job(
        session,
        RawJob(
            title="Economist",
            url="https://www.usajobs.gov/job/old",
            source=JobSource.usajobs,
            company_name="Bureau of Labor Statistics",
        ),
    )
    session.commit()

    report = await run_scan(session, role_type="full_time")

    assert old.is_active is True
    assert report.errors == ["USAJOBS: temporarily unavailable"]


@pytest.mark.asyncio
async def test_run_scan_filters_stale_jobs_by_posted_at(monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app.discovery.sources.greenhouse import GreenhouseSource
    from app.discovery.sources.github_repo import GithubRepoSource

    session = _session()
    session.add(Company(name="Acme", ats_type=AtsType.greenhouse, ats_board_id="acme"))
    session.commit()

    now = datetime.now(timezone.utc)
    raw_jobs = [
        RawJob(  # fresh: 5 days old -> kept
            title="Financial Analyst Intern",
            url="https://boards.greenhouse.io/acme/jobs/1",
            source=JobSource.greenhouse,
            company_name="Acme",
            posted_at=now - timedelta(days=5),
        ),
        RawJob(  # stale: 60 days old -> dropped
            title="Consulting Analyst Intern",
            url="https://boards.greenhouse.io/acme/jobs/2",
            source=JobSource.greenhouse,
            company_name="Acme",
            posted_at=now - timedelta(days=60),
        ),
        RawJob(  # undated -> kept (can't date it, so don't drop it)
            title="Policy Analyst Intern",
            url="https://boards.greenhouse.io/acme/jobs/3",
            source=JobSource.greenhouse,
            company_name="Acme",
        ),
    ]
    _mock_fetch(monkeypatch, GreenhouseSource, raw_jobs)
    monkeypatch.setattr(GithubRepoSource, "fetch", lambda self, company: _empty())

    report = await run_scan(session, max_age_days=21)

    assert report.jobs_found == 3
    assert report.new == 2
    assert report.stale == 1
    titles = {j.title for j in session.query(Job).all()}
    assert titles == {"Financial Analyst Intern", "Policy Analyst Intern"}


@pytest.mark.asyncio
async def test_run_scan_max_age_days_zero_disables_filter(monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app.discovery.sources.greenhouse import GreenhouseSource
    from app.discovery.sources.github_repo import GithubRepoSource

    session = _session()
    session.add(Company(name="Acme", ats_type=AtsType.greenhouse, ats_board_id="acme"))
    session.commit()

    raw_jobs = [
        RawJob(
            title="Financial Analyst Intern",
            url="https://boards.greenhouse.io/acme/jobs/1",
            source=JobSource.greenhouse,
            company_name="Acme",
            posted_at=datetime.now(timezone.utc) - timedelta(days=365),
        )
    ]
    _mock_fetch(monkeypatch, GreenhouseSource, raw_jobs)
    monkeypatch.setattr(GithubRepoSource, "fetch", lambda self, company: _empty())

    report = await run_scan(session, max_age_days=0)

    assert report.new == 1
    assert report.stale == 0
