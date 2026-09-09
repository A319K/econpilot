from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.discovery.base import RawJob
from app.discovery.pipeline import (
    classify_job_family,
    classify_role_type,
    compute_dedup_hash,
    ingest_raw_job,
    normalize_title,
)
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_normalize_title_lowercases_and_collapses_whitespace():
    assert normalize_title("  Software   Engineer  ") == "software engineer"


def test_normalize_title_strips_punctuation():
    assert normalize_title("Software Engineer, Intern!") == "software engineer intern"


def test_normalize_title_removes_year_tokens():
    assert "2026" not in normalize_title("Software Engineer Intern 2026")


def test_normalize_title_removes_season_tokens():
    result = normalize_title("Summer Software Engineer Intern")
    assert "summer" not in result


def test_normalize_title_removes_intern_dash():
    result = normalize_title("Intern - Software Engineering")
    assert "intern -" not in result
    assert "software engineering" in result


def test_normalize_title_removes_req_ids():
    result = normalize_title("Software Engineer Intern (R12345)")
    assert "r12345" not in result
    assert "12345" not in result


def test_normalize_title_equal_for_variant_phrasings():
    a = normalize_title("Software Engineer, Summer 2026")
    b = normalize_title("software engineer   summer 2026!!")
    assert a == b


def test_classify_role_type_internship():
    assert classify_role_type("Software Engineer Intern") == RoleType.internship
    assert classify_role_type("Summer Co-op - Backend") == RoleType.internship


def test_classify_role_type_full_time():
    assert classify_role_type("Senior Software Engineer") == RoleType.full_time


def test_classify_job_family_finance():
    assert classify_job_family("Investment Banking Summer Analyst") == JobFamily.finance
    assert classify_job_family("FP&A Analyst") == JobFamily.finance


def test_classify_job_family_consulting():
    assert classify_job_family("Economic Consulting Analyst") == JobFamily.consulting
    assert classify_job_family("Management Consultant") == JobFamily.consulting


def test_classify_job_family_data_analytics():
    assert classify_job_family("Data Analyst Intern") == JobFamily.data_analytics
    assert classify_job_family("Quantitative Analyst") == JobFamily.data_analytics


def test_classify_job_family_corporate():
    assert classify_job_family("Corporate Strategy Analyst") == JobFamily.corporate
    assert classify_job_family("Leadership Development Program") == JobFamily.corporate


def test_classify_job_family_policy_research():
    assert classify_job_family("Pre-Doctoral Research Assistant") == JobFamily.policy_research
    assert classify_job_family("Policy Analyst") == JobFamily.policy_research


def test_generic_title_requires_domain_evidence():
    assert (
        classify_job_family(
            "Summer Associate",
            "Join our case teams on client engagements in management consulting.",
        )
        == JobFamily.consulting
    )
    assert classify_job_family("Retail Associate", "Help customers at checkout") == JobFamily.other
    assert classify_job_family("Research Assistant", "Support a biology laboratory") == JobFamily.other
    assert (
        classify_job_family("Research Assistant", "Study monetary policy at the Federal Reserve")
        == JobFamily.policy_research
    )


def test_description_does_not_override_unrelated_title():
    assert (
        classify_job_family("Software Engineer", "Build financial modeling software")
        == JobFamily.other
    )


def test_classify_job_family_other_when_no_match():
    assert classify_job_family("Product Manager") == JobFamily.other


def test_compute_dedup_hash_is_order_stable_and_deterministic():
    h1 = compute_dedup_hash("Acme Corp", "Software Engineer Intern", "San Francisco, CA")
    h2 = compute_dedup_hash("Acme Corp", "Software Engineer Intern", "San Francisco, CA")
    assert h1 == h2


def test_compute_dedup_hash_matches_across_normalized_variants():
    h1 = compute_dedup_hash("Acme Corp", "Software Engineer Intern, Summer 2026", "San Francisco, CA")
    h2 = compute_dedup_hash("Acme Corp!", "software engineer intern  summer 2026", "san francisco, ca")
    assert h1 == h2


def test_ingest_raw_job_creates_new_job_and_company():
    session = _session()
    raw = RawJob(
        title="Data Analyst Intern",
        url="https://boards.greenhouse.io/acme/jobs/1",
        location="San Francisco, CA",
        description="Join us",
        posted_at=None,
        source=JobSource.greenhouse,
        company_name="Acme Corp",
    )

    job, created = ingest_raw_job(session, raw)
    session.commit()

    assert created is True
    assert job.company.name == "Acme Corp"
    assert job.role_type == RoleType.internship
    assert job.job_family == JobFamily.data_analytics


def test_ingest_raw_job_dedup_collision_keeps_higher_ranked_source():
    session = _session()

    github_raw = RawJob(
        title="Investment Banking Analyst - Summer 2026",
        url="https://simplify.jobs/p/aaa",
        location="San Francisco, CA",
        description="",
        source=JobSource.github_repo,
        company_name="Acme Corp",
    )
    job1, created1 = ingest_raw_job(session, github_raw)
    session.commit()

    greenhouse_raw = RawJob(
        title="Investment Banking Analyst - Summer 2026",
        url="https://boards.greenhouse.io/acme/jobs/1",
        location="San Francisco, CA",
        description="Full job description from Greenhouse",
        source=JobSource.greenhouse,
        company_name="Acme Corp",
    )
    job2, created2 = ingest_raw_job(session, greenhouse_raw)
    session.commit()

    assert created1 is True
    assert created2 is False
    assert job1.id == job2.id

    all_jobs = session.query(Job).all()
    assert len(all_jobs) == 1
    assert all_jobs[0].source == JobSource.greenhouse
    assert all_jobs[0].description == "Full job description from Greenhouse"
    assert all_jobs[0].url == "https://boards.greenhouse.io/acme/jobs/1"


def test_ingest_raw_job_lower_ranked_source_merges_missing_fields_without_replacing():
    session = _session()

    greenhouse_raw = RawJob(
        title="Software Engineer Intern - Summer 2026",
        url="https://boards.greenhouse.io/acme/jobs/1",
        location="San Francisco, CA",
        description="",
        source=JobSource.greenhouse,
        company_name="Acme Corp",
    )
    job1, _ = ingest_raw_job(session, greenhouse_raw)
    session.commit()

    github_raw = RawJob(
        title="Software Engineer Intern - Summer 2026",
        url="https://simplify.jobs/p/aaa",
        location="San Francisco, CA",
        description="Description only available from GitHub listing",
        source=JobSource.github_repo,
        company_name="Acme Corp",
    )
    job2, created2 = ingest_raw_job(session, github_raw)
    session.commit()

    assert created2 is False
    assert job1.id == job2.id
    assert job2.source == JobSource.greenhouse
    assert job2.url == "https://boards.greenhouse.io/acme/jobs/1"
    # Missing description on the primary (higher-ranked) row gets filled in.
    assert job2.description == "Description only available from GitHub listing"


def test_official_usajobs_listing_wins_dedup_against_aggregator():
    session = _session()
    mirror = RawJob(
        title="Economist",
        url="https://example.com/mirror/810000001",
        location="Washington, District of Columbia",
        source=JobSource.github_newgrad,
        company_name="Bureau of Labor Statistics",
    )
    job, created = ingest_raw_job(session, mirror)
    session.commit()
    assert created is True

    official = RawJob(
        title="Economist",
        url="https://www.usajobs.gov/job/810000001",
        location="Washington, District of Columbia",
        description="Official federal announcement",
        source=JobSource.usajobs,
        company_name="Bureau of Labor Statistics",
    )
    merged, created = ingest_raw_job(session, official)
    session.commit()

    assert created is False
    assert merged.id == job.id
    assert merged.source == JobSource.usajobs
    assert merged.url == official.url
    assert merged.description == "Official federal announcement"


def test_ingest_raw_job_reuses_existing_company_case_insensitive():
    session = _session()
    company = Company(name="Acme Corp")
    session.add(company)
    session.commit()

    raw = RawJob(
        title="Backend Engineer",
        url="https://example.com/job/1",
        source=JobSource.manual,
        company_name="acme corp",
    )
    job, _ = ingest_raw_job(session, raw)
    session.commit()

    assert job.company_id == company.id
    assert session.query(Company).count() == 1
