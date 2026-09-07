import httpx

from app.discovery.base import JobSourceClient, RawJob, SourceError
from app.models.company import Company
from app.models.job import JobSource

TIMEOUT_SECONDS = 30.0


class GreenhouseSource(JobSourceClient):
    source = JobSource.greenhouse

    async def fetch(self, company: Company | None) -> list[RawJob]:
        if company is None or not company.ats_board_id:
            raise SourceError("Greenhouse source requires a company with ats_board_id")

        url = f"https://boards-api.greenhouse.io/v1/boards/{company.ats_board_id}/jobs"

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.get(url, params={"content": "true"})
        except httpx.RequestError as exc:
            raise SourceError(f"Greenhouse request failed for {company.name}: {exc}") from exc

        if response.status_code >= 400:
            raise SourceError(
                f"Greenhouse request failed for {company.name} with status {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise SourceError(f"Greenhouse response was not JSON for {company.name}: {exc}") from exc

        jobs = data.get("jobs", [])
        raw_jobs: list[RawJob] = []
        for job in jobs:
            location = job.get("location") or {}
            raw_jobs.append(
                RawJob(
                    title=job.get("title", ""),
                    url=job.get("absolute_url", ""),
                    location=location.get("name"),
                    description=job.get("content") or "",
                    posted_at=job.get("updated_at"),
                    source=self.source,
                    company_name=company.name,
                    ats_board_id=company.ats_board_id,
                )
            )
        return raw_jobs
