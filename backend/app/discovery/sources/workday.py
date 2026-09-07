"""Workday keyless CXS JSON source.

Workday tenants expose a public, unauthenticated JSON search endpoint used by
their own career-site frontends:

    POST https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
    body: {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}

It returns {"total": int, "jobPostings": [{title, externalPath, locationsText,
postedOn, ...}]} and paginates by offset. The public apply URL for a posting is
    https://{host}/{site}{externalPath}
where externalPath already begins with "/job/...".

ats_resolve encodes the two coordinates Workday needs (the full host and the
job-board site) into ats_board_id as "host|site"; we split them back here. No
LLM, no scraping -- deterministic HTTP only.
"""

import asyncio
import random
import re
from datetime import datetime, timedelta, timezone

import httpx

from app.discovery.base import JobSourceClient, RawJob, SourceError
from app.models.company import Company
from app.models.job import JobSource

TIMEOUT_SECONDS = 30.0
_PAGE_SIZE = 20
_MAX_PAGES = 25  # cap ~500 jobs/company to avoid runaway on huge tenants

# Workday tenants share infrastructure, so a concurrent scan routinely trips
# their rate limiter (HTTP 429). Retry those transient responses a few times
# with exponential backoff (honoring Retry-After when present) so we don't lose
# a reachable board to a momentary throttle. Backoff is capped so a hostile
# Retry-After can't stall the whole scan.
_MAX_RETRIES = 3
_BACKOFF_BASE_SECONDS = 1.5
_BACKOFF_CAP_SECONDS = 20.0


async def _post_with_retry(
    client: httpx.AsyncClient, endpoint: str, payload: dict
) -> httpx.Response:
    for attempt in range(_MAX_RETRIES + 1):
        response = await client.post(endpoint, json=payload)
        if response.status_code != 429 or attempt == _MAX_RETRIES:
            return response
        retry_after = response.headers.get("Retry-After", "")
        if retry_after.isdigit():
            delay = float(retry_after)
        else:
            delay = _BACKOFF_BASE_SECONDS * (2**attempt) + random.uniform(0, 0.5)
        await asyncio.sleep(min(delay, _BACKOFF_CAP_SECONDS))
    return response

# Workday reports coarse, relative posting dates. Parse the common shapes
# best-effort; anything else stays None (scan keeps undated jobs).
_DAYS_AGO_RE = re.compile(r"(\d+)\+?\s*days?\s*ago", re.IGNORECASE)

# Some tenants 403 an obviously non-browser client.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _parse_posted_on(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip().lower()
    now = datetime.now(timezone.utc)
    if "today" in text:
        return now
    if "yesterday" in text:
        return now - timedelta(days=1)
    match = _DAYS_AGO_RE.search(text)
    if match:
        return now - timedelta(days=int(match.group(1)))
    return None


class WorkdaySource(JobSourceClient):
    source = JobSource.workday

    async def fetch(self, company: Company | None) -> list[RawJob]:
        if company is None or not company.ats_board_id:
            raise SourceError("Workday source requires a company with ats_board_id")

        host, _, site = company.ats_board_id.partition("|")
        if not host or not site:
            raise SourceError(
                f"Workday board_id for {company.name} is malformed (expected 'host|site')"
            )
        tenant = host.split(".")[0]
        endpoint = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }

        raw_jobs: list[RawJob] = []
        # Workday reports the real result count in `total` only on the *first*
        # page (later pages echo 0), so capture it once and use it as the upper
        # bound. A short page (< limit) also ends the loop.
        total: int | None = None
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, headers=headers) as client:
                for page in range(_MAX_PAGES):
                    offset = page * _PAGE_SIZE
                    response = await _post_with_retry(
                        client,
                        endpoint,
                        {
                            "appliedFacets": {},
                            "limit": _PAGE_SIZE,
                            "offset": offset,
                            "searchText": "",
                        },
                    )
                    if response.status_code >= 400:
                        raise SourceError(
                            f"Workday request failed for {company.name} with status "
                            f"{response.status_code}"
                        )
                    try:
                        data = response.json()
                    except ValueError as exc:
                        raise SourceError(
                            f"Workday response was not JSON for {company.name}: {exc}"
                        ) from exc

                    if total is None and isinstance(data.get("total"), int):
                        total = data["total"]

                    postings = data.get("jobPostings") or []
                    if not postings:
                        break

                    for posting in postings:
                        external_path = posting.get("externalPath") or ""
                        if not external_path:
                            continue
                        raw_jobs.append(
                            RawJob(
                                title=posting.get("title", ""),
                                url=f"https://{host}/{site}{external_path}",
                                location=posting.get("locationsText"),
                                description="",
                                posted_at=_parse_posted_on(posting.get("postedOn")),
                                source=self.source,
                                company_name=company.name,
                                ats_board_id=company.ats_board_id,
                            )
                        )

                    # Stop on the last page: fewer results than requested, or we
                    # have reached the total reported by the first page.
                    if len(postings) < _PAGE_SIZE:
                        break
                    if total is not None and offset + _PAGE_SIZE >= total:
                        break
        except httpx.RequestError as exc:
            raise SourceError(f"Workday request failed for {company.name}: {exc}") from exc

        return raw_jobs
