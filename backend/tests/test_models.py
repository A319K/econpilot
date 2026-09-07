from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Application, CoverLetter, Job, ResumeVersion
from app.models.company import AtsType, Company
from app.models.job import JobFamily, JobSource, RoleType


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)(), engine


def test_all_tables_created():
    _, engine = _make_session()
    tables = inspect(engine).get_table_names()

    for expected in ["companies", "jobs", "applications", "resume_versions", "cover_letters"]:
        assert expected in tables


def test_create_company_and_job():
    session, _ = _make_session()

    company = Company(name="Acme", ats_type=AtsType.greenhouse, is_target=True)
    session.add(company)
    session.commit()

    job = Job(
        company_id=company.id,
        title="SWE Intern",
        url="https://example.com/job/1",
        source=JobSource.greenhouse,
        role_type=RoleType.internship,
        job_family=JobFamily.swe,
        dedup_hash="abc123",
    )
    session.add(job)
    session.commit()

    assert job.id is not None
    assert job.company_id == company.id
    assert job.created_at is not None


def test_application_resume_and_cover_letter_relationships():
    session, _ = _make_session()

    company = Company(name="Acme")
    session.add(company)
    session.commit()

    job = Job(
        company_id=company.id,
        title="SWE Intern",
        url="https://example.com/job/2",
        source=JobSource.manual,
        role_type=RoleType.internship,
        job_family=JobFamily.other,
        dedup_hash="def456",
    )
    session.add(job)
    session.commit()

    resume = ResumeVersion(name="base", job_family=JobFamily.swe, latex_source="\\documentclass{}")
    session.add(resume)
    session.commit()

    application = Application(job_id=job.id, resume_version_id=resume.id)
    session.add(application)
    session.commit()

    cover_letter = CoverLetter(application_id=application.id, content="Dear hiring manager,")
    session.add(cover_letter)
    session.commit()

    assert application.resume_version.name == "base"
    assert cover_letter.application_id == application.id
