import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.materials import cover_letter as cover_letter_module
from app.materials import keywords as keywords_module
from app.materials import tailoring as tailoring_module
from app.materials.prepare import prepare_materials
from app.models.application import Application, ApplicationStatus
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.models.resume_version import ResumeVersion

BASE_SOURCE = """\\documentclass{article}
\\begin{document}
%% TAILOR-BEGIN:summary
Original summary.
%% TAILOR-END:summary
\\end{document}
"""


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _job(session) -> Job:
    company = Company(name="Acme")
    session.add(company)
    session.commit()

    job = Job(
        company_id=company.id,
        title="Software Engineer Intern",
        url="https://example.com/1",
        source=JobSource.manual,
        role_type=RoleType.internship,
        job_family=JobFamily.consulting,
        description="We need a Python engineer.",
        dedup_hash="h1",
    )
    session.add(job)
    session.commit()
    return job


def _base_resume(session) -> ResumeVersion:
    resume = ResumeVersion(
        name="SWE Base",
        job_family=JobFamily.consulting,
        latex_source=BASE_SOURCE,
        is_base_template=True,
        pdf_path="/fake/base.pdf",
    )
    session.add(resume)
    session.commit()
    return resume


def _mock_llm(monkeypatch):
    async def fake_complete_json(system, user, schema_hint, **kwargs):
        return {"skills": ["Python"], "responsibilities": [], "qualifications": [], "nice_to_have": []}

    async def fake_complete(system, user, **kwargs):
        return "Tailored or cover letter text."

    monkeypatch.setattr(keywords_module, "complete_json", fake_complete_json)
    monkeypatch.setattr(tailoring_module, "complete", fake_complete)
    monkeypatch.setattr(cover_letter_module, "complete", fake_complete)
    monkeypatch.setattr(tailoring_module, "compile_pdf", lambda source, name: "/fake/resume.pdf")
    monkeypatch.setattr(
        cover_letter_module, "compile_cover_letter", lambda content, company, job_id: "/fake/cl.pdf"
    )


@pytest.mark.asyncio
async def test_prepare_materials_moves_discovered_application_to_in_progress(monkeypatch):
    session = _session()
    job = _job(session)
    _base_resume(session)
    _mock_llm(monkeypatch)

    await prepare_materials(session, job.id)

    application = session.query(Application).filter(Application.job_id == job.id).one()
    assert application.status == ApplicationStatus.in_progress
    # Routed through queued -> in_progress, so two history entries.
    assert [h["to"] for h in application.status_history] == ["queued", "in_progress"]
    assert all(h["note"] == "materials prepared" for h in application.status_history)


@pytest.mark.asyncio
async def test_prepare_materials_moves_queued_application_to_in_progress(monkeypatch):
    session = _session()
    job = _job(session)
    _base_resume(session)
    _mock_llm(monkeypatch)

    application = Application(job_id=job.id, status=ApplicationStatus.queued)
    session.add(application)
    session.commit()

    await prepare_materials(session, job.id)

    session.refresh(application)
    assert application.status == ApplicationStatus.in_progress
    assert [h["to"] for h in application.status_history] == ["in_progress"]


@pytest.mark.asyncio
async def test_prepare_materials_does_not_transition_from_other_statuses(monkeypatch):
    session = _session()
    job = _job(session)
    _base_resume(session)
    _mock_llm(monkeypatch)

    application = Application(job_id=job.id, status=ApplicationStatus.ready_to_submit)
    session.add(application)
    session.commit()

    await prepare_materials(session, job.id)

    session.refresh(application)
    assert application.status == ApplicationStatus.ready_to_submit
    assert not application.status_history


@pytest.mark.asyncio
async def test_prepare_materials_does_not_transition_terminal_statuses(monkeypatch):
    session = _session()
    job = _job(session)
    _base_resume(session)
    _mock_llm(monkeypatch)

    application = Application(job_id=job.id, status=ApplicationStatus.rejected)
    session.add(application)
    session.commit()

    await prepare_materials(session, job.id)

    session.refresh(application)
    assert application.status == ApplicationStatus.rejected
    assert not application.status_history
