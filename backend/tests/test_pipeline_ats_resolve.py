"""The pipeline upgrades unknown companies to a scannable ATS from the
application URL of a discovered listing, so a one-off GitHub listing becomes a
recurring direct source on the next scan."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.discovery.base import RawJob
from app.discovery.pipeline import (
    get_or_create_company,
    ingest_raw_job,
    maybe_resolve_company_ats,
)
from app.models.company import AtsType, Company
from app.models.job import JobSource


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _github_raw(company_name: str, url: str) -> RawJob:
    return RawJob(
        title="Software Engineer Intern",
        url=url,
        location="Remote",
        source=JobSource.github_repo,
        company_name=company_name,
    )


def test_ingest_resolves_greenhouse_company_from_url():
    db = _session()
    ingest_raw_job(db, _github_raw("Acme", "https://boards.greenhouse.io/acme/jobs/1"))

    company = db.query(Company).filter(Company.name == "Acme").one()
    assert company.ats_type == AtsType.greenhouse
    assert company.ats_board_id == "acme"


def test_ingest_resolves_workday_company_with_encoded_board_id():
    db = _session()
    url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US/Intern_JR1"
    ingest_raw_job(db, _github_raw("Nvidia", url))

    company = db.query(Company).filter(Company.name == "Nvidia").one()
    assert company.ats_type == AtsType.workday
    assert company.ats_board_id == "nvidia.wd5.myworkdayjobs.com|NVIDIAExternalCareerSite"


def test_ingest_leaves_unrecognized_host_unknown():
    db = _session()
    ingest_raw_job(db, _github_raw("Stripe", "https://stripe.com/jobs/listing/123"))

    company = db.query(Company).filter(Company.name == "Stripe").one()
    assert company.ats_type == AtsType.unknown
    assert company.ats_board_id is None


def test_resolution_does_not_override_known_company():
    db = _session()
    # A hand-seeded company already resolved to greenhouse/stripe.
    seeded = Company(
        name="Stripe", ats_type=AtsType.greenhouse, ats_board_id="stripe", is_target=True
    )
    db.add(seeded)
    db.flush()

    # A GitHub listing points at a *different* (wrong) board id; must be ignored.
    changed = maybe_resolve_company_ats(seeded, "https://jobs.lever.co/someoneelse/x")
    assert changed is False
    assert seeded.ats_type == AtsType.greenhouse
    assert seeded.ats_board_id == "stripe"


def test_greenhouse_without_board_id_stays_unknown():
    db = _session()
    company = get_or_create_company(db, "Malformed")
    # Greenhouse host but no path segment / board id -> not scannable, leave it.
    changed = maybe_resolve_company_ats(company, "https://boards.greenhouse.io/")
    assert changed is False
    assert company.ats_type == AtsType.unknown
