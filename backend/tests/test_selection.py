import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.materials import selection as selection_module
from app.materials.selection import SelectionError, select_resume
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.models.resume_version import ResumeVersion


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _job(session, job_family=JobFamily.swe) -> Job:
    company = Company(name="Acme")
    session.add(company)
    session.commit()

    job = Job(
        company_id=company.id,
        title="Software Engineer Intern",
        url="https://example.com/1",
        source=JobSource.greenhouse,
        role_type=RoleType.internship,
        job_family=job_family,
        dedup_hash="h1",
    )
    session.add(job)
    session.commit()
    return job


def _resume(session, name, job_family, keywords=None, is_base_template=True) -> ResumeVersion:
    resume = ResumeVersion(
        name=name,
        job_family=job_family,
        latex_source="\\documentclass{article}\\begin{document}x\\end{document}",
        is_base_template=is_base_template,
        keywords=keywords or [],
    )
    session.add(resume)
    session.commit()
    return resume


@pytest.mark.asyncio
async def test_select_resume_raises_when_no_base_templates_exist():
    session = _session()
    job = _job(session)

    with pytest.raises(SelectionError):
        await select_resume(session, job, {})


@pytest.mark.asyncio
async def test_select_resume_returns_sole_candidate_without_llm_call(monkeypatch):
    session = _session()
    job = _job(session)
    resume = _resume(session, "SWE Base", JobFamily.swe)

    async def fail(*args, **kwargs):
        raise AssertionError("LLM should not be called with a single candidate")

    monkeypatch.setattr(selection_module, "complete_json", fail)

    result = await select_resume(session, job, {})
    assert result.id == resume.id


@pytest.mark.asyncio
async def test_select_resume_filters_candidates_by_job_family():
    session = _session()
    job = _job(session, job_family=JobFamily.data)
    data_resume = _resume(session, "Data Base", JobFamily.data)
    _resume(session, "SWE Base", JobFamily.swe)

    result = await select_resume(session, job, {})
    assert result.id == data_resume.id


@pytest.mark.asyncio
async def test_select_resume_falls_back_to_all_base_templates_when_none_match_family():
    session = _session()
    job = _job(session, job_family=JobFamily.cloud_infra)
    swe_resume = _resume(session, "SWE Base", JobFamily.swe)

    result = await select_resume(session, job, {})
    assert result.id == swe_resume.id


@pytest.mark.asyncio
async def test_select_resume_uses_llm_choice_when_valid(monkeypatch):
    session = _session()
    job = _job(session)
    _resume(session, "Backend Focus", JobFamily.swe, keywords=["backend"])
    frontend = _resume(session, "Frontend Focus", JobFamily.swe, keywords=["frontend"])

    async def fake_complete_json(system, user, schema_hint, **kwargs):
        return {"resume_id": frontend.id, "reasoning": "matches frontend keywords"}

    monkeypatch.setattr(selection_module, "complete_json", fake_complete_json)

    result = await select_resume(session, job, {"skills": ["frontend"]})
    assert result.id == frontend.id


@pytest.mark.asyncio
async def test_select_resume_ignores_llm_choice_referencing_invalid_id(monkeypatch):
    session = _session()
    job = _job(session)
    backend = _resume(session, "Backend Focus", JobFamily.swe, keywords=["backend", "api"])
    _resume(session, "Frontend Focus", JobFamily.swe, keywords=["frontend", "react"])

    async def fake_complete_json(system, user, schema_hint, **kwargs):
        return {"resume_id": 999999, "reasoning": "hallucinated id"}

    monkeypatch.setattr(selection_module, "complete_json", fake_complete_json)

    result = await select_resume(session, job, {"skills": ["backend", "api"]})
    assert result.id == backend.id  # deterministic fallback by keyword overlap


@pytest.mark.asyncio
async def test_select_resume_falls_back_on_llm_error(monkeypatch):
    from app.llm.client import LLMError

    session = _session()
    job = _job(session)
    backend = _resume(session, "Backend Focus", JobFamily.swe, keywords=["backend"])
    _resume(session, "Frontend Focus", JobFamily.swe, keywords=["frontend"])

    async def fake_complete_json(system, user, schema_hint, **kwargs):
        raise LLMError("boom")

    monkeypatch.setattr(selection_module, "complete_json", fake_complete_json)

    result = await select_resume(session, job, {"skills": ["backend"]})
    assert result.id == backend.id


@pytest.mark.asyncio
async def test_select_resume_fallback_is_deterministic_tie_break_by_lowest_id(monkeypatch):
    session = _session()
    job = _job(session)
    first = _resume(session, "A", JobFamily.swe, keywords=["backend"])
    _resume(session, "B", JobFamily.swe, keywords=["backend"])

    async def fake_complete_json(system, user, schema_hint, **kwargs):
        raise Exception("boom")

    monkeypatch.setattr(selection_module, "complete_json", fake_complete_json)

    result = await select_resume(session, job, {"skills": ["backend"]})
    assert result.id == first.id
