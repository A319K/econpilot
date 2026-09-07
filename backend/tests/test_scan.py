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
            title="Software Engineer Intern",
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
            title="Backend Engineer",
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
            title="Senior Software Engineer",
            url="https://boards.greenhouse.io/acme/jobs/1",
            source=JobSource.greenhouse,
            company_name="Acme",
        ),
        RawJob(
            title="Software Engineer Intern",
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
    assert session.query(Job).first().title == "Senior Software Engineer"


@pytest.mark.asyncio
async def test_run_scan_internship_sources_from_github_only(monkeypatch):
    from app.discovery.sources.github_repo import GithubRepoSource
    from app.discovery.sources.greenhouse import GreenhouseSource

    session = _session()
    session.add(Company(name="Acme", ats_type=AtsType.greenhouse, ats_board_id="acme"))
    session.commit()

    # This ATS posting would be ingested if an internship scan swept the ATS
    # sources - it must not be, so the assertions below expect it absent.
    ats_jobs = [
        RawJob(
            title="Software Engineer Intern",
            url="https://boards.greenhouse.io/acme/jobs/1",
            source=JobSource.greenhouse,
            company_name="Acme",
        )
    ]
    _mock_fetch(monkeypatch, GreenhouseSource, ats_jobs)

    async def _github(self, company):
        return [
            RawJob(
                title="Backend Engineering Intern",
                url="https://example.com/gh-intern",
                source=JobSource.github_repo,
                company_name="Acme",
            )
        ]

    monkeypatch.setattr(GithubRepoSource, "fetch", _github)

    report = await run_scan(session, role_type="internship")

    assert report.companies_scanned == 0  # ATS sweep skipped for internships
    assert session.query(Job).count() == 1
    assert session.query(Job).first().source == JobSource.github_repo


@pytest.mark.asyncio
async def test_run_scan_newgrad_source_ingested_as_full_time(monkeypatch):
    from app.discovery.sources.github_repo import GithubNewGradSource, GithubRepoSource

    session = _session()

    async def _newgrad(self, company):
        return [
            RawJob(
                title="Software Engineer, New Grad",
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
async def test_run_scan_drops_fulltime_other_noise(monkeypatch):
    from app.discovery.sources.greenhouse import GreenhouseSource
    from app.discovery.sources.github_repo import GithubRepoSource

    session = _session()
    session.add(Company(name="Acme", ats_type=AtsType.greenhouse, ats_board_id="acme"))
    session.commit()

    raw_jobs = [
        RawJob(  # full-time non-tech -> dropped as noise
            title="Registered Nurse",
            url="https://boards.greenhouse.io/acme/jobs/1",
            source=JobSource.greenhouse,
            company_name="Acme",
        ),
        RawJob(  # full-time tech -> kept
            title="Senior Software Engineer",
            url="https://boards.greenhouse.io/acme/jobs/2",
            source=JobSource.greenhouse,
            company_name="Acme",
        ),
        RawJob(  # internship, even non-tech family -> always kept
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
    assert report.filtered == 1
    assert report.new == 2
    titles = {j.title for j in session.query(Job).all()}
    assert titles == {"Senior Software Engineer", "Marketing Intern"}


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
                title="Software Engineer Intern",
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
            title="Software Engineer Intern",
            url="https://boards.greenhouse.io/acme/jobs/1",
            source=JobSource.greenhouse,
            company_name="Acme",
            posted_at=now - timedelta(days=5),
        ),
        RawJob(  # stale: 60 days old -> dropped
            title="Backend Engineer Intern",
            url="https://boards.greenhouse.io/acme/jobs/2",
            source=JobSource.greenhouse,
            company_name="Acme",
            posted_at=now - timedelta(days=60),
        ),
        RawJob(  # undated -> kept (can't date it, so don't drop it)
            title="Platform Engineer Intern",
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
    assert titles == {"Software Engineer Intern", "Platform Engineer Intern"}


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
            title="Software Engineer Intern",
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
