"""SimplifyJobs internship-list source.

Reads the repo's structured `.github/scripts/listings.json` (not the rendered
README table): each record carries an absolute `date_posted` epoch, the real
application `url`, an `active` flag, and `locations`. Absolute dates are what
Phase B's seasonal month-bucketing depends on, and the application urls are
what the pipeline resolves into scannable ATS companies.
"""

import json
import logging
from datetime import datetime, timezone
from typing import NamedTuple
from urllib.parse import urlparse, urlunparse

import httpx

from app.config import get_settings
from app.discovery.base import JobSourceClient, RawJob, SourceError
from app.models.company import Company
from app.models.job import JobSource

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 30.0

# Query params Simplify appends to application links for tracking; strip them so
# the same posting on the direct link and a mirror dedups to one url.
_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "ref"}


def strip_simplify_wrapper(url: str) -> str:
    """Strip Simplify tracking query params from an application URL."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    kept = [
        pair
        for pair in parsed.query.split("&")
        if pair.split("=")[0] not in _TRACKING_PARAMS
    ]
    return urlunparse(parsed._replace(query="&".join(kept)))


def _posted_at(epoch: object) -> datetime | None:
    if not epoch:
        return None
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc)  # type: ignore[arg-type]
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def parse_listings_json(text: str, *, active_only: bool = True) -> list[dict]:
    """Parse SimplifyJobs listings.json into normalized row dicts.

    Skips records missing a url/company/title, and (by default) roles no longer
    active. Callers doing historical analysis pass active_only=False to keep the
    full dated history.
    """
    try:
        records = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise SourceError(f"listings.json was not valid JSON: {exc}") from exc
    if not isinstance(records, list):
        raise SourceError("listings.json was not a JSON array")

    rows: list[dict] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if active_only and not rec.get("active"):
            continue
        url = rec.get("url")
        company_name = rec.get("company_name")
        title = rec.get("title")
        if not url or not company_name or not title:
            continue
        locations = rec.get("locations")
        location = ", ".join(locations) if isinstance(locations, list) and locations else None
        rows.append(
            {
                "company_name": company_name.strip(),
                "title": title.strip(),
                "location": location,
                "url": strip_simplify_wrapper(url),
                "posted_at": _posted_at(rec.get("date_posted")),
            }
        )
    return rows


class FeedSpec(NamedTuple):
    owner: str
    name: str
    branch: str
    path: str


def _parse_feed(spec: str) -> FeedSpec | None:
    # Path itself contains slashes (.github/scripts/listings.json), so split
    # only the first three fields off and keep the remainder as the path.
    parts = spec.split("/", 3)
    if len(parts) != 4 or not all(part.strip() for part in parts):
        logger.warning("ignoring malformed discovery feed spec %r", spec)
        return None
    return FeedSpec(*(part.strip() for part in parts))


def _parse_feed_specs(specs: list[str], seed: list[FeedSpec] | None = None) -> list[FeedSpec]:
    """Parse "owner/name/branch/path" specs into FeedSpecs, deduped, preserving
    any seed feeds first."""
    feeds = list(seed or [])
    seen = set(feeds)
    for spec in specs or []:
        parsed = _parse_feed(spec)
        if parsed is not None and parsed not in seen:
            feeds.append(parsed)
            seen.add(parsed)
    return feeds


def discovery_feeds(settings) -> list[FeedSpec]:
    """The primary internship feed plus any configured additional feeds (deduped)."""
    primary = FeedSpec(
        settings.github_repo_owner,
        settings.github_repo_name,
        settings.github_repo_branch,
        settings.github_repo_listings_path,
    )
    return _parse_feed_specs(settings.github_additional_feeds, seed=[primary])


def newgrad_feeds(settings) -> list[FeedSpec]:
    """Full-time new-grad feeds (SimplifyJobs New-Grad-Positions and any others)."""
    return _parse_feed_specs(settings.github_newgrad_feeds)


def listings_url(owner: str, name: str, branch: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{owner}/{name}/{branch}/{path}"


async def fetch_all_rows(
    active_only: bool = True, feeds: list[FeedSpec] | None = None
) -> list[dict]:
    """Fetch and merge parsed rows across the given feeds (defaulting to the
    internship feeds). A feed that fails is logged and skipped; SourceError is
    raised only if *every* feed fails (so one dead mirror never blanks out
    discovery)."""
    if feeds is None:
        feeds = discovery_feeds(get_settings())
    rows: list[dict] = []
    errors: list[str] = []
    for feed in feeds:
        url = listings_url(feed.owner, feed.name, feed.branch, feed.path)
        try:
            text = await fetch_listings_text(url)
            rows.extend(parse_listings_json(text, active_only=active_only))
        except SourceError as exc:
            errors.append(f"{feed.owner}/{feed.name}: {exc}")
            logger.warning("discovery feed %s/%s failed: %s", feed.owner, feed.name, exc)
    if not rows and errors:
        raise SourceError("; ".join(errors))
    return rows


async def fetch_listings_text(url: str) -> str:
    """GET the raw listings.json text, raising SourceError on any failure."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.get(url)
    except httpx.RequestError as exc:
        raise SourceError(f"GitHub repo request failed: {exc}") from exc
    if response.status_code >= 400:
        raise SourceError(f"GitHub repo request failed with status {response.status_code}")
    return response.text


def _rows_to_raw_jobs(rows: list[dict], source: JobSource) -> list[RawJob]:
    return [
        RawJob(
            title=row["title"],
            url=row["url"],
            location=row["location"],
            description="",
            posted_at=row["posted_at"],
            source=source,
            company_name=row["company_name"],
            ats_board_id=None,
        )
        for row in rows
    ]


class GithubRepoSource(JobSourceClient):
    """SimplifyJobs internship listings -> internship roles."""

    source = JobSource.github_repo

    async def fetch(self, company: Company | None) -> list[RawJob]:
        rows = await fetch_all_rows(active_only=True)
        return _rows_to_raw_jobs(rows, self.source)


class GithubNewGradSource(JobSourceClient):
    """SimplifyJobs New-Grad-Positions listings -> full-time new-grad roles."""

    source = JobSource.github_newgrad

    async def fetch(self, company: Company | None) -> list[RawJob]:
        rows = await fetch_all_rows(active_only=True, feeds=newgrad_feeds(get_settings()))
        return _rows_to_raw_jobs(rows, self.source)
