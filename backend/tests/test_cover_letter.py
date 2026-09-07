import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.materials import cover_letter as cover_letter_module
from app.materials.cover_letter import (
    build_profile_summary,
    generate_cover_letter,
    render_letter_latex,
)
from app.models.application import Application
from app.models.company import Company
from app.models.cover_letter import CoverLetter
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.profile import (
    Education,
    Personal,
    Profile,
    Skills,
    StandardAnswers,
    WorkExperience,
)


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _job_and_application(session):
    company = Company(name="Acme")
    session.add(company)
    session.commit()

    job = Job(
        company_id=company.id,
        title="Software Engineer Intern",
        url="https://example.com/1",
        source=JobSource.greenhouse,
        role_type=RoleType.internship,
        job_family=JobFamily.consulting,
        dedup_hash="h1",
    )
    session.add(job)
    session.commit()

    application = Application(job_id=job.id)
    session.add(application)
    session.commit()
    return job, application


def _profile() -> Profile:
    return Profile(
        personal=Personal(name="Jordan Test", email="jordan@example.com", phone="555", city="Boston", state="MA"),
        education=[Education(school="Test U", degree="BS", major="CS", start="2023", end="2027")],
        work_experience=[
            WorkExperience(company="Initech", title="SWE Intern", start="2025", end="2025", bullets=["Built X", "Shipped Y"])
        ],
        projects=[],
        skills=Skills(languages=["Python"], frameworks=["FastAPI"], tools=["Docker"]),
        standard_answers=StandardAnswers(
            work_authorization="citizen", requires_sponsorship=False, willing_to_relocate=True, graduation_date="2027-05"
        ),
    )


def test_build_profile_summary_includes_key_fields():
    summary = build_profile_summary(_profile())

    assert "Jordan Test" in summary
    assert "Test U" in summary
    assert "Initech" in summary
    assert "Built X" in summary
    assert "Python" in summary


def test_render_letter_latex_escapes_special_chars():
    content = "I led a team on Acme & Co's project (50% faster)."
    result = render_letter_latex(content)

    assert "\\&" in result
    assert "\\%" in result
    assert "\\documentclass" in result
    assert "\\begin{document}" in result
    assert "\\end{document}" in result


def test_render_letter_latex_preserves_paragraph_breaks():
    content = "First paragraph.\n\nSecond paragraph."
    result = render_letter_latex(content)

    assert result.index("First paragraph.") < result.index("Second paragraph.")
    assert "\n\n" in result.split("\\begin{document}\n", 1)[1]


@pytest.mark.asyncio
async def test_generate_cover_letter_persists_row_with_needs_review_true(monkeypatch):
    session = _session()
    job, application = _job_and_application(session)

    monkeypatch.setattr(cover_letter_module, "get_profile", _profile)

    async def fake_complete(system, user, **kwargs):
        return "This is a specific, professional cover letter body about the role."

    monkeypatch.setattr(cover_letter_module, "complete", fake_complete)
    monkeypatch.setattr(cover_letter_module, "compile_cover_letter", lambda content, company, job_id: "/fake/cl.pdf")

    result = await generate_cover_letter(session, application, job, {"skills": ["Python"]})

    assert isinstance(result, CoverLetter)
    assert result.needs_review is True
    assert result.application_id == application.id
    assert result.pdf_path == "/fake/cl.pdf"
    assert "cover letter body" in result.content


@pytest.mark.asyncio
async def test_generate_cover_letter_passes_job_and_keyword_context(monkeypatch):
    session = _session()
    job, application = _job_and_application(session)

    monkeypatch.setattr(cover_letter_module, "get_profile", _profile)

    captured = {}

    async def fake_complete(system, user, **kwargs):
        captured["user"] = user
        return "Body."

    monkeypatch.setattr(cover_letter_module, "complete", fake_complete)
    monkeypatch.setattr(cover_letter_module, "compile_cover_letter", lambda content, company, job_id: "/fake/cl.pdf")

    await generate_cover_letter(session, application, job, {"skills": ["Python", "AWS"]})

    assert "Software Engineer Intern" in captured["user"]
    assert "Acme" in captured["user"]
    assert "Python" in captured["user"]
