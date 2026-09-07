"""Tests for the SimplifyJobs listings.json source (structured feed)."""

import json
from datetime import timezone

import httpx
import pytest

from app.config import get_settings
from app.discovery.base import SourceError
from app.discovery.sources.github_repo import (
    GithubRepoSource,
    discovery_feeds,
    fetch_all_rows,
    parse_listings_json,
    strip_simplify_wrapper,
)

# A few records mirroring the real listings.json shape: one active Greenhouse
# role, one active Workday role, one closed role, and one with a Simplify
# tracking wrapper on the url.
_SAMPLE = [
    {
        "company_name": "Acme Corp",
        "title": "Software Engineer Intern",
        "url": "https://boards.greenhouse.io/acme/jobs/123?utm_source=Simplify&ref=Simplify",
        "locations": ["New York, NY"],
        "date_posted": 1704067200,  # 2024-01-01 UTC
        "active": True,
    },
    {
        "company_name": "Nvidia",
        "title": "Performance Engineering Intern",
        "url": "https://nvidia.wd5.myworkdayjobs.com/site/job/US/Intern_JR1",
        "locations": ["Santa Clara, CA", "Remote"],
        "date_posted": 1735689600,  # 2025-01-01 UTC
        "active": True,
    },
    {
        "company_name": "Closed Co",
        "title": "Data Intern",
        "url": "https://jobs.lever.co/closedco/x",
        "locations": [],
        "date_posted": 1700000000,
        "active": False,
    },
    {
        # Missing url -> skipped even though active.
        "company_name": "No Link Inc",
        "title": "Intern",
        "url": "",
        "locations": ["Boston, MA"],
        "date_posted": 1700000000,
        "active": True,
    },
]


def _sample_text() -> str:
    return json.dumps(_SAMPLE)


def test_parse_listings_json_keeps_only_active_with_urls():
    rows = parse_listings_json(_sample_text())
    assert [r["company_name"] for r in rows] == ["Acme Corp", "Nvidia"]


def test_parse_listings_json_strips_tracking_params():
    rows = parse_listings_json(_sample_text())
    acme = rows[0]
    assert "utm_source" not in acme["url"]
    assert "ref=Simplify" not in acme["url"]
    assert acme["url"].startswith("https://boards.greenhouse.io/acme/jobs/123")


def test_parse_listings_json_joins_locations():
    rows = parse_listings_json(_sample_text())
    assert rows[0]["location"] == "New York, NY"
    assert rows[1]["location"] == "Santa Clara, CA, Remote"


def test_parse_listings_json_converts_epoch_to_utc_datetime():
    rows = parse_listings_json(_sample_text())
    posted = rows[0]["posted_at"]
    assert posted is not None
    assert posted.tzinfo is not None
    assert posted.astimezone(timezone.utc).year == 2024


def test_parse_listings_json_active_only_false_keeps_closed():
    rows = parse_listings_json(_sample_text(), active_only=False)
    # Closed Co is included now; the url-less record is still dropped.
    assert "Closed Co" in [r["company_name"] for r in rows]
    assert "No Link Inc" not in [r["company_name"] for r in rows]


def test_parse_listings_json_rejects_non_json():
    with pytest.raises(SourceError):
        parse_listings_json("<html>not json</html>")


def test_parse_listings_json_rejects_non_array():
    with pytest.raises(SourceError):
        parse_listings_json('{"company_name": "X"}')


def test_strip_simplify_wrapper_keeps_non_tracking_params():
    url = "https://example.com/apply?utm_source=Simplify&ref=Simplify&keep=1"
    result = strip_simplify_wrapper(url)
    assert "utm_source" not in result
    assert "ref=Simplify" not in result
    assert "keep=1" in result


def _single_feed(monkeypatch):
    """Pin the source to just the primary feed so per-parse assertions are
    deterministic regardless of the configured additional feeds."""
    from app.discovery.sources import github_repo as gh

    settings = get_settings()
    monkeypatch.setattr(settings, "github_additional_feeds", [], raising=False)
    monkeypatch.setattr(gh, "get_settings", lambda: settings)


def _mock_transport(monkeypatch, handler):
    from app.discovery.sources import github_repo as gh

    real_client = httpx.AsyncClient

    def fake_async_client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(gh.httpx, "AsyncClient", fake_async_client)


def test_discovery_feeds_includes_primary_and_additional(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "github_repo_owner", "SimplifyJobs", raising=False)
    monkeypatch.setattr(settings, "github_repo_name", "Summer2026-Internships", raising=False)
    monkeypatch.setattr(settings, "github_repo_branch", "dev", raising=False)
    monkeypatch.setattr(settings, "github_repo_listings_path", "x/listings.json", raising=False)
    monkeypatch.setattr(
        settings, "github_additional_feeds",
        ["vanshb03/Summer2026-Internships/dev/.github/scripts/listings.json", "bad-spec"],
        raising=False,
    )

    feeds = discovery_feeds(settings)
    owners = [f.owner for f in feeds]
    assert owners == ["SimplifyJobs", "vanshb03"]  # malformed "bad-spec" dropped
    # Path keeps its own slashes.
    assert feeds[1].path == ".github/scripts/listings.json"


@pytest.mark.asyncio
async def test_github_repo_fetch_builds_raw_jobs(monkeypatch):
    _single_feed(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        assert "raw.githubusercontent.com" in str(request.url)
        assert "listings.json" in str(request.url)
        return httpx.Response(200, text=_sample_text())

    _mock_transport(monkeypatch, handler)

    jobs = await GithubRepoSource().fetch(None)

    assert [j.company_name for j in jobs] == ["Acme Corp", "Nvidia"]
    assert jobs[0].source.value == "github_repo"


@pytest.mark.asyncio
async def test_fetch_all_rows_merges_multiple_feeds(monkeypatch):
    from app.discovery.sources import github_repo as gh

    settings = get_settings()
    monkeypatch.setattr(settings, "github_repo_owner", "SimplifyJobs", raising=False)
    monkeypatch.setattr(settings, "github_repo_name", "primary", raising=False)
    monkeypatch.setattr(
        settings, "github_additional_feeds",
        ["vanshb03/second/dev/.github/scripts/listings.json"], raising=False,
    )
    monkeypatch.setattr(gh, "get_settings", lambda: settings)

    def handler(request: httpx.Request) -> httpx.Response:
        # Each feed serves one distinct active company.
        if "/primary/" in str(request.url):
            return httpx.Response(200, text=json.dumps([_SAMPLE[0]]))  # Acme
        return httpx.Response(200, text=json.dumps([_SAMPLE[1]]))  # Nvidia

    _mock_transport(monkeypatch, handler)

    rows = await fetch_all_rows()
    assert sorted(r["company_name"] for r in rows) == ["Acme Corp", "Nvidia"]


@pytest.mark.asyncio
async def test_fetch_all_rows_tolerates_one_failing_feed(monkeypatch):
    from app.discovery.sources import github_repo as gh

    settings = get_settings()
    monkeypatch.setattr(settings, "github_repo_name", "primary", raising=False)
    monkeypatch.setattr(
        settings, "github_additional_feeds",
        ["vanshb03/dead/dev/.github/scripts/listings.json"], raising=False,
    )
    monkeypatch.setattr(gh, "get_settings", lambda: settings)

    def handler(request: httpx.Request) -> httpx.Response:
        if "/dead/" in str(request.url):
            return httpx.Response(404, text="gone")
        return httpx.Response(200, text=json.dumps([_SAMPLE[0]]))

    _mock_transport(monkeypatch, handler)

    rows = await fetch_all_rows()
    assert [r["company_name"] for r in rows] == ["Acme Corp"]  # survivor still returned


@pytest.mark.asyncio
async def test_fetch_all_rows_raises_when_every_feed_fails(monkeypatch):
    _single_feed(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    _mock_transport(monkeypatch, handler)

    with pytest.raises(SourceError):
        await fetch_all_rows()
