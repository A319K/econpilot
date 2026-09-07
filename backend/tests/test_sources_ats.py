import json
from pathlib import Path

import httpx
import pytest

from app.discovery.base import SourceError
from app.discovery.sources.ashby import AshbySource
from app.discovery.sources.greenhouse import GreenhouseSource
from app.discovery.sources.lever import LeverSource
from app.models.company import AtsType, Company

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict | list:
    with (FIXTURES / name).open() as f:
        return json.load(f)


def _install_transport(monkeypatch, module, handler):
    real_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", fake_async_client)


def _company(ats_type: AtsType, board_id: str = "acme") -> Company:
    return Company(id=1, name="Acme", ats_type=ats_type, ats_board_id=board_id)


@pytest.mark.asyncio
async def test_greenhouse_fetch_parses_fixture(monkeypatch):
    from app.discovery.sources import greenhouse as gh_module

    def handler(request: httpx.Request) -> httpx.Response:
        assert "boards-api.greenhouse.io" in str(request.url)
        return httpx.Response(200, json=_load("greenhouse_jobs.json"))

    _install_transport(monkeypatch, gh_module, handler)

    jobs = await GreenhouseSource().fetch(_company(AtsType.greenhouse))

    assert len(jobs) == 2
    assert jobs[0].title == "Software Engineer Intern - Summer 2026"
    assert jobs[0].location == "San Francisco, CA"
    assert jobs[0].url == "https://boards.greenhouse.io/acme/jobs/4001"
    assert "software engineer" in jobs[0].description.lower()
    assert jobs[0].posted_at is not None


@pytest.mark.asyncio
async def test_greenhouse_raises_source_error_on_failure(monkeypatch):
    from app.discovery.sources import greenhouse as gh_module

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server error")

    _install_transport(monkeypatch, gh_module, handler)

    with pytest.raises(SourceError):
        await GreenhouseSource().fetch(_company(AtsType.greenhouse))


@pytest.mark.asyncio
async def test_greenhouse_requires_board_id():
    company = Company(id=1, name="Acme", ats_type=AtsType.greenhouse, ats_board_id=None)
    with pytest.raises(SourceError):
        await GreenhouseSource().fetch(company)


@pytest.mark.asyncio
async def test_lever_fetch_parses_fixture(monkeypatch):
    from app.discovery.sources import lever as lever_module

    def handler(request: httpx.Request) -> httpx.Response:
        assert "api.lever.co" in str(request.url)
        return httpx.Response(200, json=_load("lever_postings.json"))

    _install_transport(monkeypatch, lever_module, handler)

    jobs = await LeverSource().fetch(_company(AtsType.lever))

    assert len(jobs) == 2
    assert jobs[0].title == "Data Science Intern"
    assert jobs[0].location == "New York, NY"
    assert jobs[0].url == "https://jobs.lever.co/acme/abc-123"
    assert jobs[0].posted_at is not None


@pytest.mark.asyncio
async def test_lever_raises_source_error_on_failure(monkeypatch):
    from app.discovery.sources import lever as lever_module

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    _install_transport(monkeypatch, lever_module, handler)

    with pytest.raises(SourceError):
        await LeverSource().fetch(_company(AtsType.lever))


@pytest.mark.asyncio
async def test_ashby_fetch_parses_fixture(monkeypatch):
    from app.discovery.sources import ashby as ashby_module

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert "api.ashbyhq.com" in str(request.url)
        return httpx.Response(200, json=_load("ashby_jobs.json"))

    _install_transport(monkeypatch, ashby_module, handler)

    jobs = await AshbySource().fetch(_company(AtsType.ashby))

    assert len(jobs) == 2
    assert jobs[0].title == "Machine Learning Intern"
    assert jobs[0].location == "Remote - US"
    assert jobs[0].url == "https://jobs.ashbyhq.com/acme/job-1"
    assert jobs[0].posted_at is not None


@pytest.mark.asyncio
async def test_ashby_raises_source_error_on_failure(monkeypatch):
    from app.discovery.sources import ashby as ashby_module

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    _install_transport(monkeypatch, ashby_module, handler)

    with pytest.raises(SourceError):
        await AshbySource().fetch(_company(AtsType.ashby))
