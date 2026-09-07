"""Tests for the Workday keyless CXS JSON source."""

import json

import httpx
import pytest

from app.discovery.base import SourceError
from app.discovery.sources.workday import WorkdaySource
from app.models.company import AtsType, Company

_BOARD_ID = "nvidia.wd5.myworkdayjobs.com|NVIDIAExternalCareerSite"


def _company(board_id: str | None = _BOARD_ID) -> Company:
    return Company(name="Nvidia", ats_type=AtsType.workday, ats_board_id=board_id)


def _posting(n: int) -> dict:
    return {
        "title": f"Intern {n}",
        "externalPath": f"/job/US/Intern_{n}",
        "locationsText": "Santa Clara, CA",
        "postedOn": "Posted 5 Days Ago",
    }


def _mock_transport(monkeypatch, handler):
    from app.discovery.sources import workday as wd

    real_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(wd.httpx, "AsyncClient", fake_async_client)


@pytest.mark.asyncio
async def test_fetch_paginates_and_builds_urls(monkeypatch):
    # A full first page forces a second request; later pages echo total=0 (the
    # real Workday quirk) so a short page must be what ends the loop.
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs" in str(request.url)
        offset = json.loads(request.content)["offset"]
        if offset == 0:
            return httpx.Response(
                200, json={"total": 21, "jobPostings": [_posting(n) for n in range(20)]}
            )
        if offset == 20:
            return httpx.Response(200, json={"total": 0, "jobPostings": [_posting(20)]})
        return httpx.Response(200, json={"jobPostings": []})

    _mock_transport(monkeypatch, handler)

    jobs = await WorkdaySource().fetch(_company())

    assert len(jobs) == 21  # 20 from page one + 1 from page two, despite total=0 echo
    assert jobs[0].url == (
        "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US/Intern_0"
    )
    assert jobs[0].location == "Santa Clara, CA"
    assert jobs[0].source.value == "workday"
    assert jobs[0].posted_at is not None  # "Posted 5 Days Ago" parsed


@pytest.mark.asyncio
async def test_fetch_stops_on_total(monkeypatch):
    # A full page (== limit) whose count already equals `total` must stop
    # without issuing a needless second request.
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(
            200, json={"total": 20, "jobPostings": [_posting(n) for n in range(20)]}
        )

    _mock_transport(monkeypatch, handler)

    jobs = await WorkdaySource().fetch(_company())

    assert len(jobs) == 20
    assert calls["n"] == 1  # total reached after the first page, no second request


@pytest.mark.asyncio
async def test_fetch_requires_board_id():
    with pytest.raises(SourceError):
        await WorkdaySource().fetch(_company(board_id=None))


@pytest.mark.asyncio
async def test_fetch_rejects_malformed_board_id(monkeypatch):
    with pytest.raises(SourceError):
        await WorkdaySource().fetch(_company(board_id="nohostorsite"))


@pytest.mark.asyncio
async def test_fetch_raises_on_http_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    _mock_transport(monkeypatch, handler)

    with pytest.raises(SourceError):
        await WorkdaySource().fetch(_company())
