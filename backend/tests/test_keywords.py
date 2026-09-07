import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.materials import keywords as keywords_module
from app.materials.keywords import EMPTY_KEYWORDS, extract_keywords
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _job(session, **overrides) -> Job:
    company = Company(name="Acme")
    session.add(company)
    session.commit()

    defaults = dict(
        company_id=company.id,
        title="Software Engineer Intern",
        url="https://example.com/1",
        source=JobSource.greenhouse,
        role_type=RoleType.internship,
        job_family=JobFamily.consulting,
        description="We need someone skilled in Python and AWS.",
        dedup_hash="h1",
    )
    defaults.update(overrides)
    job = Job(**defaults)
    session.add(job)
    session.commit()
    return job


@pytest.mark.asyncio
async def test_extract_keywords_returns_empty_structure_without_llm_call_when_no_description(monkeypatch):
    session = _session()
    job = _job(session, description=None)

    async def fail(*args, **kwargs):
        raise AssertionError("LLM should not be called for an empty description")

    monkeypatch.setattr(keywords_module, "complete_json", fail)

    result = await extract_keywords(session, job)

    assert result == EMPTY_KEYWORDS
    assert job.jd_keywords == EMPTY_KEYWORDS


@pytest.mark.asyncio
async def test_extract_keywords_returns_empty_structure_for_blank_description(monkeypatch):
    session = _session()
    job = _job(session, description="   ")

    async def fail(*args, **kwargs):
        raise AssertionError("LLM should not be called for a blank description")

    monkeypatch.setattr(keywords_module, "complete_json", fail)

    result = await extract_keywords(session, job)
    assert result == EMPTY_KEYWORDS


@pytest.mark.asyncio
async def test_extract_keywords_calls_llm_and_caches_on_job(monkeypatch):
    session = _session()
    job = _job(session)

    calls = {"count": 0}

    async def fake_complete_json(system, user, schema_hint, **kwargs):
        calls["count"] += 1
        return {
            "skills": ["Python", "AWS"],
            "responsibilities": ["Build services"],
            "qualifications": ["BS in CS"],
            "nice_to_have": ["Kubernetes"],
        }

    monkeypatch.setattr(keywords_module, "complete_json", fake_complete_json)

    result = await extract_keywords(session, job)

    assert calls["count"] == 1
    assert result["skills"] == ["Python", "AWS"]
    assert job.jd_keywords == result

    # Second call should use the cached value and not call the LLM again.
    result2 = await extract_keywords(session, job)
    assert calls["count"] == 1
    assert result2 == result


@pytest.mark.asyncio
async def test_extract_keywords_normalizes_missing_keys(monkeypatch):
    session = _session()
    job = _job(session)

    async def fake_complete_json(system, user, schema_hint, **kwargs):
        return {"skills": ["Python"]}  # missing other keys

    monkeypatch.setattr(keywords_module, "complete_json", fake_complete_json)

    result = await extract_keywords(session, job)

    assert result["skills"] == ["Python"]
    assert result["responsibilities"] == []
    assert result["qualifications"] == []
    assert result["nice_to_have"] == []


@pytest.mark.asyncio
async def test_extract_keywords_truncates_long_description(monkeypatch):
    from app.config import get_settings

    session = _session()
    long_description = "x" * 10000
    job = _job(session, description=long_description)

    captured = {}

    async def fake_complete_json(system, user, schema_hint, **kwargs):
        captured["user"] = user
        return dict(EMPTY_KEYWORDS)

    monkeypatch.setattr(keywords_module, "complete_json", fake_complete_json)

    await extract_keywords(session, job)

    max_chars = get_settings().jd_description_max_chars
    # The user prompt embeds the (truncated) description plus a title line,
    # so it should never approach the full 10000-char description length.
    assert len(captured["user"]) <= max_chars + 200
