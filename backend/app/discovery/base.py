from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel

from app.models.company import Company
from app.models.job import JobSource


class SourceError(Exception):
    """Raised when a source fails to fetch or parse jobs for a company."""


class RawJob(BaseModel):
    title: str
    url: str
    location: str | None = None
    description: str = ""
    posted_at: datetime | None = None
    source: JobSource
    company_name: str
    ats_board_id: str | None = None


class JobSourceClient(ABC):
    """Base class for a discovery source. Sources stay dumb: fetch raw jobs,
    the pipeline handles normalization, dedup, classification, and scoring."""

    source: JobSource

    @abstractmethod
    async def fetch(self, company: Company | None) -> list[RawJob]:
        raise NotImplementedError
