from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.application import Application, ApplicationStatus
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.models.mixins import utcnow
from app.tracking.stats import compute_stats


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _company(session, name="Acme") -> Company:
    company = Company(name=name)
    session.add(company)
    session.commit()
    return company


_job_counter = 0


def _job(session, company, role_type=RoleType.internship, discovered_at=None) -> Job:
    global _job_counter
    _job_counter += 1
    job = Job(
        company_id=company.id,
        title="SWE Intern",
        url=f"https://example.com/{company.id}-{role_type.value}-{_job_counter}",
        source=JobSource.manual,
        role_type=role_type,
        job_family=JobFamily.swe,
        dedup_hash=f"h{company.id}-{role_type.value}-{_job_counter}",
        discovered_at=discovered_at or utcnow(),
    )
    session.add(job)
    session.commit()
    return job


def _application(session, job, status=ApplicationStatus.discovered, submitted_at=None) -> Application:
    application = Application(job_id=job.id, status=status, submitted_at=submitted_at)
    session.add(application)
    session.commit()
    return application


def test_compute_stats_on_empty_db_returns_zeroed_structure():
    session = _session()

    stats = compute_stats(session)

    assert stats.all.counts_by_status["discovered"] == 0
    assert stats.all.submitted_per_day == []
    assert stats.all.funnel.submitted == 0
    assert stats.all.funnel.conversion_rates["submitted_to_oa"] == 0.0
    assert stats.all.avg_hours_to_submit is None
    assert stats.all.top_companies == []


def test_counts_by_status_reflects_current_statuses():
    session = _session()
    company = _company(session)
    job1 = _job(session, company)
    job2 = _job(session, company)
    _application(session, job1, status=ApplicationStatus.discovered)
    _application(session, job2, status=ApplicationStatus.queued)

    stats = compute_stats(session)

    assert stats.all.counts_by_status["discovered"] == 1
    assert stats.all.counts_by_status["queued"] == 1
    assert stats.all.counts_by_status["offer"] == 0


def test_counts_split_correctly_by_role_type():
    session = _session()
    company = _company(session)
    intern_job = _job(session, company, role_type=RoleType.internship)
    ft_job = _job(session, company, role_type=RoleType.full_time)
    _application(session, intern_job, status=ApplicationStatus.queued)
    _application(session, ft_job, status=ApplicationStatus.queued)

    stats = compute_stats(session)

    assert stats.internship.counts_by_status["queued"] == 1
    assert stats.full_time.counts_by_status["queued"] == 1
    assert stats.all.counts_by_status["queued"] == 2


def test_funnel_counts_and_conversion_rates():
    session = _session()
    company = _company(session)
    now = utcnow()

    for _ in range(4):
        job = _job(session, company)
        _application(session, job, status=ApplicationStatus.submitted, submitted_at=now)
    for _ in range(2):
        job = _job(session, company)
        _application(session, job, status=ApplicationStatus.oa, submitted_at=now)
    job = _job(session, company)
    _application(session, job, status=ApplicationStatus.interview, submitted_at=now)

    stats = compute_stats(session)
    funnel = stats.all.funnel

    assert funnel.submitted == 4
    assert funnel.oa == 2
    assert funnel.interview == 1
    assert funnel.offer == 0
    assert funnel.conversion_rates["submitted_to_oa"] == 0.5
    assert funnel.conversion_rates["oa_to_interview"] == 0.5
    assert funnel.conversion_rates["interview_to_offer"] == 0.0  # guarded, no ZeroDivisionError


def test_funnel_guards_division_by_zero_when_no_submissions():
    session = _session()
    company = _company(session)
    job = _job(session, company)
    _application(session, job, status=ApplicationStatus.discovered)

    stats = compute_stats(session)

    assert stats.all.funnel.submitted == 0
    assert stats.all.funnel.conversion_rates["submitted_to_oa"] == 0.0


def test_submitted_per_day_only_counts_last_30_days():
    session = _session()
    company = _company(session)
    now = utcnow()

    recent_job = _job(session, company)
    _application(session, recent_job, status=ApplicationStatus.submitted, submitted_at=now)

    old_job = _job(session, company)
    _application(
        session, old_job, status=ApplicationStatus.submitted, submitted_at=now - timedelta(days=60)
    )

    stats = compute_stats(session)
    total_recent = sum(d.count for d in stats.all.submitted_per_day)

    assert total_recent == 1


def test_submitted_per_day_groups_by_date():
    session = _session()
    company = _company(session)
    now = utcnow()

    for _ in range(3):
        job = _job(session, company)
        _application(session, job, status=ApplicationStatus.submitted, submitted_at=now)

    stats = compute_stats(session)

    assert len(stats.all.submitted_per_day) == 1
    assert stats.all.submitted_per_day[0].count == 3


def test_avg_hours_to_submit_computes_correctly():
    session = _session()
    company = _company(session)
    now = utcnow()

    job = _job(session, company, discovered_at=now - timedelta(hours=10))
    _application(session, job, status=ApplicationStatus.submitted, submitted_at=now)

    stats = compute_stats(session)

    assert stats.all.avg_hours_to_submit == pytest_approx(10.0)


def pytest_approx(value, tol=0.1):
    class _Approx:
        def __eq__(self, other):
            return abs(other - value) < tol

    return _Approx()


def test_avg_hours_to_submit_is_none_when_nothing_submitted():
    session = _session()
    company = _company(session)
    job = _job(session, company)
    _application(session, job, status=ApplicationStatus.discovered)

    stats = compute_stats(session)
    assert stats.all.avg_hours_to_submit is None


def test_avg_hours_to_submit_ignores_non_submitted_applications():
    session = _session()
    company = _company(session)
    now = utcnow()

    submitted_job = _job(session, company, discovered_at=now - timedelta(hours=5))
    _application(session, submitted_job, status=ApplicationStatus.submitted, submitted_at=now)

    unsubmitted_job = _job(session, company, discovered_at=now - timedelta(hours=1000))
    _application(session, unsubmitted_job, status=ApplicationStatus.discovered)

    stats = compute_stats(session)
    assert stats.all.avg_hours_to_submit == pytest_approx(5.0)


def test_top_companies_ordered_by_application_count():
    session = _session()
    big_co = _company(session, "BigCo")
    small_co = _company(session, "SmallCo")

    for _ in range(3):
        job = _job(session, big_co)
        _application(session, job)
    job = _job(session, small_co)
    _application(session, job)

    stats = compute_stats(session)
    top = stats.all.top_companies

    assert top[0].company_name == "BigCo"
    assert top[0].count == 3
    assert top[1].company_name == "SmallCo"
    assert top[1].count == 1


def test_top_companies_limited_to_10():
    session = _session()
    for i in range(15):
        company = _company(session, f"Company{i}")
        job = _job(session, company)
        _application(session, job)

    stats = compute_stats(session)
    assert len(stats.all.top_companies) == 10
