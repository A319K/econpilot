import httpx

from app.discovery.base import JobSourceClient, RawJob, SourceError
from app.models.company import Company
from app.models.job import JobSource

TIMEOUT_SECONDS = 30.0


class AshbySource(JobSourceClient):
    source = JobSource.ashby

    async def fetch(self, company: Company | None) -> list[RawJob]:
        if company is None or not company.ats_board_id:
            raise SourceError("Ashby source requires a company with ats_board_id")

        url = f"https://api.ashbyhq.com/posting-api/job-board/{company.ats_board_id}"

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.get(url)
        except httpx.RequestError as exc:
            raise SourceError(f"Ashby request failed for {company.name}: {exc}") from exc

        if response.status_code >= 400:
            raise SourceError(
                f"Ashby request failed for {company.name} with status {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise SourceError(f"Ashby response was not JSON for {company.name}: {exc}") from exc

        jobs = data.get("jobs", [])
        raw_jobs: list[RawJob] = []
        for job in jobs:
            raw_jobs.append(
                RawJob(
                    title=job.get("title", ""),
                    url=job.get("jobUrl", ""),
                    location=job.get("location"),
                    description=job.get("descriptionPlain") or job.get("descriptionHtml") or "",
                    posted_at=job.get("publishedAt"),
                    source=self.source,
                    company_name=company.name,
                    ats_board_id=company.ats_board_id,
                )
            )
        return raw_jobs
