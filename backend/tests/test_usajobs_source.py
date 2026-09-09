import json
from pathlib import Path

import httpx
import pytest

from app.discovery.base import SourceError
from app.discovery.sources import usajobs
from app.discovery.sources.usajobs import UsaJobsSource, parse_search_payload
from app.models.job import JobSource

FIXTURE = Path(__file__).parent / "fixtures" / "usajobs_search.json"


def _payload():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_search_payload_maps_official_fields_and_publication_date():
    jobs, pages = parse_search_payload(_payload())

    assert pages == 1
    assert len(jobs) == 2
    assert jobs[0].source == JobSource.usajobs
    assert jobs[0].company_name == "Bureau of Labor Statistics"
    assert jobs[0].location == "Washington, District of Columbia"
    assert jobs[0].url == "https://www.usajobs.gov/job/810000001"
    assert jobs[0].posted_at.isoformat() == "2026-09-08T00:00:00+00:00"
    assert "Analyze employment and price data." in jobs[0].description
    assert jobs[1].posted_at is None


def test_parse_search_payload_rejects_unknown_shape():
    with pytest.raises(SourceError, match="without search results"):
        parse_search_payload({"message": "maintenance"})


@pytest.mark.asyncio
async def test_fetch_sends_required_headers_filters_and_paginates(monkeypatch):
    requests: list[dict] = []
    first = _payload()
    first["SearchResult"]["UserArea"]["NumberOfPages"] = "2"
    second = _payload()
    second["SearchResult"]["SearchResultItems"] = [
        second["SearchResult"]["SearchResultItems"][0]
    ]

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, *, headers, params):
            requests.append({"url": url, "headers": headers, "params": params})
            payload = first if params["Page"] == 1 else second
            return httpx.Response(200, json=payload)

    monkeypatch.setattr(usajobs.httpx, "AsyncClient", lambda **_kwargs: FakeClient())

    jobs = await UsaJobsSource(
        api_key="secret", user_agent="student@example.com", date_posted_days=21
    ).fetch(None)

    assert len(requests) == 2
    assert requests[0]["headers"] == {
        "Host": "data.usajobs.gov",
        "User-Agent": "student@example.com",
        "Authorization-Key": "secret",
    }
    assert requests[0]["params"]["JobCategoryCode"] == "0110"
    assert requests[0]["params"]["WhoMayApply"] == "Public"
    assert requests[0]["params"]["DatePosted"] == 21
    assert requests[0]["params"]["ResultsPerPage"] == 500
    assert {request["params"]["Page"] for request in requests} == {1, 2}
    assert len(jobs) == 2  # duplicate PositionURI on page two is collapsed


@pytest.mark.asyncio
async def test_fetch_requires_key_and_registration_email():
    with pytest.raises(SourceError, match="both an API key"):
        await UsaJobsSource(api_key="", user_agent="").fetch(None)


@pytest.mark.asyncio
async def test_fetch_turns_auth_failure_into_actionable_error(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return httpx.Response(403)

    monkeypatch.setattr(usajobs.httpx, "AsyncClient", lambda **_kwargs: FakeClient())

    with pytest.raises(SourceError, match="rejected the API key"):
        await UsaJobsSource(api_key="bad", user_agent="student@example.com").fetch(None)
