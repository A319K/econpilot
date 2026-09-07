import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.materials import cover_letter as cover_letter_module
from app.materials import keywords as keywords_module
from app.materials import selection as selection_module
from app.materials import tailoring as tailoring_module
from app.materials.prepare import PrepareError, prepare_materials
from app.models.application import Application
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.models.resume_version import ResumeVersion

BASE_SOURCE = """\\documentclass{article}
\\begin{document}
%% TAILOR-BEGIN:summary
Original summary.
%% TAILOR-END:summary
%% TAILOR-BEGIN:skills
Python
%% TAILOR-END:skills
\\end{document}
"""


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _job(session, description="We need a Python engineer.") -> Job:
    company = Company(name="Acme")
    session.add(company)
    session.commit()

    job = Job(
        company_id=company.id,
        title="Software Engineer Intern",
        url="https://example.com/1",
        source=JobSource.greenhouse,
        role_type=RoleType.internship,
        job_family=JobFamily.swe,
        description=description,
        dedup_hash="h1",
    )
    session.add(job)
    session.commit()
    return job


def _base_resume(session) -> ResumeVersion:
    resume = ResumeVersion(
        name="SWE Base",
        job_family=JobFamily.swe,
        latex_source=BASE_SOURCE,
        is_base_template=True,
        pdf_path="/fake/base.pdf",
    )
    session.add(resume)
    session.commit()
    return resume


def _mock_llm(monkeypatch, tailored_output="Tailored!", cl_output="Cover letter body."):
    async def fake_complete_json(system, user, schema_hint, **kwargs):
        return {"skills": ["Python"], "responsibilities": [], "qualifications": [], "nice_to_have": []}

    async def fake_complete(system, user, **kwargs):
        if "Region:" in user:
            return tailored_output
        return cl_output

    monkeypatch.setattr(keywords_module, "complete_json", fake_complete_json)
    monkeypatch.setattr(tailoring_module, "complete", fake_complete)
    monkeypatch.setattr(cover_letter_module, "complete", fake_complete)
    monkeypatch.setattr(tailoring_module, "compile_pdf", lambda source, name: "/fake/resume.pdf")
    monkeypatch.setattr(
        cover_letter_module, "compile_cover_letter", lambda content, company, job_id: "/fake/cl.pdf"
    )


@pytest.mark.asyncio
async def test_prepare_materials_raises_for_missing_job():
    session = _session()
    with pytest.raises(PrepareError):
        await prepare_materials(session, 999999)


@pytest.mark.asyncio
async def test_prepare_materials_creates_application_when_missing(monkeypatch):
    session = _session()
    job = _job(session)
    _base_resume(session)
    _mock_llm(monkeypatch)

    assert session.query(Application).filter(Application.job_id == job.id).one_or_none() is None

    report = await prepare_materials(session, job.id)

    application = session.query(Application).filter(Application.job_id == job.id).one()
    assert application.resume_version_id == report.resume_used
    assert application.cover_letter_id == report.cover_letter_id


@pytest.mark.asyncio
async def test_prepare_materials_full_flow_with_tailoring_and_cover_letter(monkeypatch):
    session = _session()
    job = _job(session)
    base = _base_resume(session)
    _mock_llm(monkeypatch)

    report = await prepare_materials(session, job.id, tailor=True, cover_letter=True)

    assert report.tailored is True
    assert report.resume_used != base.id
    assert set(report.regions_changed) == {"summary", "skills"}
    assert report.cover_letter_id is not None
    assert "resume" in report.pdf_paths
    assert "cover_letter" in report.pdf_paths
    # keyword extraction (1) + resume selection (0, single candidate) +
    # tailoring (2 regions) + cover letter (1) = 4
    assert report.llm_calls_made == 4


@pytest.mark.asyncio
async def test_prepare_materials_skips_tailoring_when_requested(monkeypatch):
    session = _session()
    job = _job(session)
    base = _base_resume(session)
    _mock_llm(monkeypatch)

    report = await prepare_materials(session, job.id, tailor=False, cover_letter=True)

    assert report.tailored is False
    assert report.resume_used == base.id
    assert report.regions_changed == []


@pytest.mark.asyncio
async def test_prepare_materials_skips_cover_letter_when_requested(monkeypatch):
    session = _session()
    job = _job(session)
    _base_resume(session)
    _mock_llm(monkeypatch)

    report = await prepare_materials(session, job.id, tailor=False, cover_letter=False)

    assert report.cover_letter_id is None
    assert "cover_letter" not in report.pdf_paths


@pytest.mark.asyncio
async def test_prepare_materials_reuses_existing_application(monkeypatch):
    session = _session()
    job = _job(session)
    _base_resume(session)
    _mock_llm(monkeypatch)

    existing = Application(job_id=job.id, notes="pre-existing")
    session.add(existing)
    session.commit()

    await prepare_materials(session, job.id, tailor=False, cover_letter=False)

    applications = session.query(Application).filter(Application.job_id == job.id).all()
    assert len(applications) == 1
    assert applications[0].id == existing.id
    assert applications[0].notes == "pre-existing"


@pytest.mark.asyncio
async def test_prepare_materials_skips_keyword_llm_call_when_no_description(monkeypatch):
    session = _session()
    job = _job(session, description=None)
    _base_resume(session)
    _mock_llm(monkeypatch)

    report = await prepare_materials(session, job.id, tailor=False, cover_letter=False)

    # keyword extraction (0, no description) + selection (0, single
    # candidate) + cover letter (0, skipped) = 0
    assert report.llm_calls_made == 0
