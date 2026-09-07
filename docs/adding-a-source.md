# Adding a new job source

EconPilot's discovery layer is a set of small, dumb **source clients**: each one
fetches raw jobs from one place (an ATS API, a scraped list) and hands them to
the shared pipeline, which owns normalization, dedup, classification, and
scoring. Adding a source means writing one `fetch()` method and registering it.

This guide walks through adding an **ATS-backed source** (the common case, like
Greenhouse/Lever/Ashby). Non-ATS sources — e.g. the GitHub internship list — use
the same interface but are wired in slightly differently (see the end).

## 1. The interface

Every source subclasses `JobSourceClient` (`app/discovery/base.py`):

```python
class JobSourceClient(ABC):
    source: JobSource                      # the enum tag stamped on every RawJob

    @abstractmethod
    async def fetch(self, company: Company | None) -> list[RawJob]:
        ...
```

`fetch()` returns a list of `RawJob`:

```python
class RawJob(BaseModel):
    title: str
    url: str
    location: str | None = None
    description: str = ""
    posted_at: datetime | None = None
    source: JobSource
    company_name: str
    ats_board_id: str | None = None
```

Rules of the road:

- **Stay dumb.** Don't dedup, score, or classify — return everything the API
  gives you. The pipeline does the rest.
- **Fail loudly with `SourceError`.** Wrap network/parse failures in
  `SourceError(...)`; the scan orchestrator catches it per-company, records it
  in `ScanReport.errors`, and (critically) will *not* treat that company's jobs
  as "vanished". Never let a source raise a bare exception.
- **Be `async`.** Use `httpx.AsyncClient` with a timeout; the scan runs sources
  concurrently under a semaphore.

## 2. Write the client

Model it on `app/discovery/sources/greenhouse.py`. Skeleton:

```python
# app/discovery/sources/acme.py
import httpx
from app.discovery.base import JobSourceClient, RawJob, SourceError
from app.models.company import Company
from app.models.job import JobSource

TIMEOUT_SECONDS = 30.0

class AcmeSource(JobSourceClient):
    source = JobSource.acme          # add this enum value (step 3)

    async def fetch(self, company: Company | None) -> list[RawJob]:
        if company is None or not company.ats_board_id:
            raise SourceError("Acme source requires a company with ats_board_id")

        url = f"https://api.acme.com/boards/{company.ats_board_id}/jobs"
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.get(url)
        except httpx.RequestError as exc:
            raise SourceError(f"Acme request failed for {company.name}: {exc}") from exc
        if response.status_code >= 400:
            raise SourceError(f"Acme {company.name} -> HTTP {response.status_code}")

        return [
            RawJob(
                title=j["title"],
                url=j["url"],
                location=j.get("location"),
                description=j.get("content", ""),
                source=self.source,
                company_name=company.name,
                ats_board_id=company.ats_board_id,
            )
            for j in response.json().get("jobs", [])
        ]
```

## 3. Register it

Two enums and one map:

1. **`JobSource`** in `app/models/job.py` — add `acme = "acme"`. (This is the
   tag stored on each job; new values need an Alembic migration only if you've
   made it a native DB enum — the project uses `native_enum=False`, so a string
   value needs no schema change, but add a migration if you change columns.)
2. **`AtsType`** in `app/models/company.py` — add `acme = "acme"` so companies
   can declare `ats_type: acme`.
3. **`_ATS_SOURCE_MAP`** in `app/discovery/scan.py` — map the ATS type to the
   client:

   ```python
   _ATS_SOURCE_MAP = {
       AtsType.greenhouse: GreenhouseSource,
       AtsType.lever: LeverSource,
       AtsType.ashby: AshbySource,
       AtsType.acme: AcmeSource,      # <-- new
   }
   ```

That's it — the scan orchestrator now fetches Acme for any company whose
`ats_type` is `acme`.

## 4. Test with a committed fixture

Follow the pattern in `tests/test_sources_ats.py` with a captured API response
in `tests/fixtures/`:

- Save one real (anonymized) API response as `tests/fixtures/acme_jobs.json`.
- In the test, mock the HTTP call to return that fixture and assert `fetch()`
  produces the expected `RawJob` list — correct field mapping, empty-location
  handling, and that a non-200 raises `SourceError`.

Fixture tests are fast, deterministic, and run in CI. Keep fixtures free of real
personal data (see `SECURITY.md`).

## 5. Live-verify before relying on it

Fixtures prove your parsing; they don't prove the endpoint shape is still
correct. Once before shipping, point the source at a real board id and run an
actual scan:

```bash
cd backend
.venv/bin/python -m pytest tests/test_sources_ats.py -q     # fixtures green
# then a live check against a real company:
.venv/bin/uvicorn app.main:app &
curl -X POST localhost:8000/scan -H 'Content-Type: application/json' -d '{}'
```

Confirm real jobs come back with sane titles/URLs/locations. ATS APIs change
their response shape and rate limits without notice — a live pass is the only
way to catch that.

## Non-ATS sources

A source that isn't keyed by a company (like the GitHub internship list,
`app/discovery/sources/github_repo.py`) implements the same `JobSourceClient`
interface but is invoked directly by the scan orchestrator rather than through
`_ATS_SOURCE_MAP`, and its `fetch()` takes `company=None`. If you're adding one,
mirror `GithubRepoSource`: it parses the raw README table into `RawJob`s tagged
`JobSource.github_repo`, and the pipeline/scan special-cases it (e.g. those jobs
are always classified `internship` and are never deactivated by the watcher,
since the upstream list lags reality).
