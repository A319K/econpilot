import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.materials import tailoring as tailoring_module
from app.materials.latex import LatexError
from app.materials.tailoring import tailor_resume
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.models.resume_version import ResumeVersion

BASE_SOURCE = """\\documentclass{article}
\\begin{document}

%% TAILOR-BEGIN:summary
Original summary.
%% TAILOR-END:summary

%% TAILOR-BEGIN:skills
Python, TypeScript
%% TAILOR-END:skills

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
        source=JobSource.greenhouse,
        role_type=RoleType.internship,
        job_family=JobFamily.swe,
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


@pytest.mark.asyncio
async def test_tailor_resume_creates_child_row_when_compile_succeeds(monkeypatch):
    session = _session()
    job = _job(session)
    base = _base_resume(session)

    async def fake_complete(system, user, **kwargs):
        return "New tailored content."

    monkeypatch.setattr(tailoring_module, "complete", fake_complete)
    monkeypatch.setattr(tailoring_module, "compile_pdf", lambda source, name: "/fake/output.pdf")

    result = await tailor_resume(session, base, job, {"skills": ["Python"]})

    assert result.id != base.id
    assert result.parent_id == base.id
    assert result.is_base_template is False
    assert "New tailored content." in result.latex_source
    assert result.pdf_path == "/fake/output.pdf"


@pytest.mark.asyncio
async def test_tailor_resume_returns_base_when_llm_output_rejected(monkeypatch):
    session = _session()
    job = _job(session)
    base = _base_resume(session)

    async def fake_complete(system, user, **kwargs):
        return "\\input{/etc/passwd}"  # dangerous command, should be rejected

    compile_calls = {"count": 0}

    def fake_compile(source, name):
        compile_calls["count"] += 1
        return "/fake/output.pdf"

    monkeypatch.setattr(tailoring_module, "complete", fake_complete)
    monkeypatch.setattr(tailoring_module, "compile_pdf", fake_compile)

    result = await tailor_resume(session, base, job, {})

    assert result.id == base.id
    assert compile_calls["count"] == 0  # never even attempted a compile


@pytest.mark.asyncio
async def test_tailor_resume_returns_base_when_llm_call_raises(monkeypatch):
    session = _session()
    job = _job(session)
    base = _base_resume(session)

    async def fake_complete(system, user, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(tailoring_module, "complete", fake_complete)

    result = await tailor_resume(session, base, job, {})
    assert result.id == base.id


@pytest.mark.asyncio
async def test_tailor_resume_reverts_failing_region_and_recompiles(monkeypatch):
    session = _session()
    job = _job(session)
    base = _base_resume(session)

    async def fake_complete(system, user, **kwargs):
        return "Tailored content."

    calls = []

    def fake_compile(source, name):
        calls.append(source)
        # Fail only when both regions are still tailored (first attempt);
        # succeed once at least one region has been reverted.
        if "Original summary." in source or "Python, TypeScript" in source:
            return "/fake/output.pdf"
        raise LatexError("compile failed")

    monkeypatch.setattr(tailoring_module, "complete", fake_complete)
    monkeypatch.setattr(tailoring_module, "compile_pdf", fake_compile)

    result = await tailor_resume(session, base, job, {})

    assert result.id != base.id
    assert result.parent_id == base.id
    # One of the two regions should have been reverted to its original text.
    assert ("Original summary." in result.latex_source) or ("Python, TypeScript" in result.latex_source)
    assert len(calls) >= 2  # first full attempt failed, retry succeeded


@pytest.mark.asyncio
async def test_tailor_resume_falls_back_to_base_when_all_compiles_fail(monkeypatch):
    session = _session()
    job = _job(session)
    base = _base_resume(session)

    async def fake_complete(system, user, **kwargs):
        return "Tailored content."

    def fake_compile(source, name):
        raise LatexError("always fails")

    monkeypatch.setattr(tailoring_module, "complete", fake_complete)
    monkeypatch.setattr(tailoring_module, "compile_pdf", fake_compile)

    result = await tailor_resume(session, base, job, {})

    assert result.id == base.id
    assert result.pdf_path == "/fake/base.pdf"


@pytest.mark.asyncio
async def test_tailor_resume_only_changes_regions_actually_modified(monkeypatch):
    session = _session()
    job = _job(session)
    base = _base_resume(session)

    async def fake_complete(system, user, **kwargs):
        # Echo back the original content for "summary" untouched, but
        # change "skills" - simulate by inspecting the user prompt.
        if "Region: summary" in user:
            return "Original summary."
        return "Rewritten skills."

    monkeypatch.setattr(tailoring_module, "complete", fake_complete)
    monkeypatch.setattr(tailoring_module, "compile_pdf", lambda source, name: "/fake/output.pdf")

    result = await tailor_resume(session, base, job, {})

    from app.materials.regions import parse_regions

    regions = parse_regions(result.latex_source)
    assert regions["summary"].strip() == "Original summary."
    assert regions["skills"].strip() == "Rewritten skills."
