from datetime import datetime, timezone

import httpx

from app.discovery.base import JobSourceClient, RawJob, SourceError
from app.models.company import Company
from app.models.job import JobSource

TIMEOUT_SECONDS = 30.0


class LeverSource(JobSourceClient):
    source = JobSource.lever

    async def fetch(self, company: Company | None) -> list[RawJob]:
        if company is None or not company.ats_board_id:
            raise SourceError("Lever source requires a company with ats_board_id")

        url = f"https://api.lever.co/v0/postings/{company.ats_board_id}"

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.get(url, params={"mode": "json"})
        except httpx.RequestError as exc:
            raise SourceError(f"Lever request failed for {company.name}: {exc}") from exc

        if response.status_code >= 400:
            raise SourceError(
                f"Lever request failed for {company.name} with status {response.status_code}"
            )

        try:
            postings = response.json()
        except ValueError as exc:
            raise SourceError(f"Lever response was not JSON for {company.name}: {exc}") from exc

        raw_jobs: list[RawJob] = []
        for posting in postings:
            categories = posting.get("categories") or {}
            created_at_ms = posting.get("createdAt")
            posted_at = (
                datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc)
                if created_at_ms
                else None
            )
            raw_jobs.append(
                RawJob(
                    title=posting.get("text", ""),
                    url=posting.get("hostedUrl", ""),
                    location=categories.get("location"),
                    description=posting.get("descriptionPlain") or posting.get("description") or "",
                    posted_at=posted_at,
                    source=self.source,
                    company_name=company.name,
                    ats_board_id=company.ats_board_id,
                )
            )
        return raw_jobs
