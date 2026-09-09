"""Official USAJOBS search source for federal Economist (series 0110) roles.

The Search API returns currently open announcements and exposes a reliable
``PublicationStartDate``. EconPilot keeps that date as ``posted_at`` and links
directly to ``PositionURI`` so USAJOBS remains visibly credited as the source.
An API key and the registration email are required by USAJOBS; this source is
optional and the rest of discovery remains keyless.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.config import get_settings
from app.discovery.base import JobSourceClient, RawJob, SourceError
from app.models.company import Company
from app.models.job import JobSource

SEARCH_URL = "https://data.usajobs.gov/api/search"
ECONOMIST_SERIES = "0110"
RESULTS_PER_PAGE = 500
MAX_PAGES = 20  # USAJOBS documents a 10,000-row maximum per query.
TIMEOUT_SECONDS = 30.0


def _parse_datetime(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _description(descriptor: dict[str, Any]) -> str:
    details = descriptor.get("UserArea", {}).get("Details", {})
    if not isinstance(details, dict):
        details = {}
    parts = [
        descriptor.get("QualificationSummary"),
        details.get("JobSummary"),
        details.get("MajorDuties"),
        details.get("Education"),
        details.get("Requirements"),
    ]
    return "\n\n".join(str(part).strip() for part in parts if str(part or "").strip())


def parse_search_payload(payload: Any) -> tuple[list[RawJob], int]:
    """Map one USAJOBS Search response page into the shared RawJob contract."""
    if not isinstance(payload, dict):
        raise SourceError("USAJOBS returned an unexpected response.")
    result = payload.get("SearchResult")
    if not isinstance(result, dict):
        raise SourceError("USAJOBS returned a response without search results.")
    items = result.get("SearchResultItems")
    if not isinstance(items, list):
        raise SourceError("USAJOBS returned a response without a job list.")

    raw_jobs: list[RawJob] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        descriptor = item.get("MatchedObjectDescriptor")
        if not isinstance(descriptor, dict):
            continue
        title = str(descriptor.get("PositionTitle") or "").strip()
        url = str(descriptor.get("PositionURI") or "").strip()
        organization = str(
            descriptor.get("OrganizationName") or descriptor.get("DepartmentName") or ""
        ).strip()
        if not title or not url or not organization:
            continue
        location = str(descriptor.get("PositionLocationDisplay") or "").strip() or None
        raw_jobs.append(
            RawJob(
                title=title,
                url=url,
                location=location,
                description=_description(descriptor),
                posted_at=_parse_datetime(descriptor.get("PublicationStartDate")),
                source=JobSource.usajobs,
                company_name=organization,
            )
        )

    user_area = result.get("UserArea")
    pages_value = user_area.get("NumberOfPages", 1) if isinstance(user_area, dict) else 1
    try:
        pages = max(1, int(pages_value))
    except (TypeError, ValueError):
        pages = 1
    return raw_jobs, min(pages, MAX_PAGES)


class UsaJobsSource(JobSourceClient):
    source = JobSource.usajobs

    def __init__(
        self,
        api_key: str | None = None,
        user_agent: str | None = None,
        date_posted_days: int | None = None,
    ):
        settings = get_settings()
        self.api_key = settings.usajobs_api_key if api_key is None else api_key
        self.user_agent = settings.usajobs_user_agent if user_agent is None else user_agent
        self.date_posted_days = date_posted_days

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.user_agent)

    async def fetch(self, company: Company | None) -> list[RawJob]:
        if not self.configured:
            raise SourceError(
                "USAJOBS needs both an API key and the email used to request it."
            )

        headers = {
            "Host": "data.usajobs.gov",
            "User-Agent": self.user_agent,
            "Authorization-Key": self.api_key,
        }
        base_params: dict[str, str | int] = {
            "JobCategoryCode": ECONOMIST_SERIES,
            "WhoMayApply": "Public",
            "Fields": "Full",
            "ResultsPerPage": RESULTS_PER_PAGE,
            "SortField": "opendate",
            "SortDirection": "Desc",
        }
        if self.date_posted_days is not None and self.date_posted_days > 0:
            base_params["DatePosted"] = min(self.date_posted_days, 60)

        jobs: list[RawJob] = []
        pages = 1
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                page = 1
                while page <= pages:
                    response = await client.get(
                        SEARCH_URL, headers=headers, params={**base_params, "Page": page}
                    )
                    if response.status_code in (401, 403):
                        raise SourceError(
                            "USAJOBS rejected the API key or registration email. "
                            "Check both values and try again."
                        )
                    if response.status_code >= 400:
                        raise SourceError(
                            f"USAJOBS could not load jobs (HTTP {response.status_code}). "
                            "Try again later."
                        )
                    page_jobs, pages = parse_search_payload(response.json())
                    jobs.extend(page_jobs)
                    page += 1
        except SourceError:
            raise
        except (httpx.RequestError, ValueError) as exc:
            raise SourceError(
                "USAJOBS could not be reached or returned unreadable data. Try again later."
            ) from exc

        # A defensive URL dedup protects against an item appearing on a page
        # boundary while the live result set changes during pagination.
        return list({job.url: job for job in jobs}.values())
