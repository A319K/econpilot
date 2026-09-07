"""ATS detection from an application URL, and the adapter factory."""

from urllib.parse import urlparse

from app.agent.adapters.ashby import AshbyAdapter
from app.agent.adapters.base import Adapter
from app.agent.adapters.generic import GenericAdapter
from app.agent.adapters.greenhouse import GreenhouseAdapter
from app.agent.adapters.lever import LeverAdapter
from app.agent.adapters.workday import WorkdayAdapter

ATS_TYPES = ("greenhouse", "lever", "ashby", "workday", "generic")

# Host substrings -> ATS name. Checked against the URL host (case-insensitive).
_HOST_PATTERNS: list[tuple[str, str]] = [
    ("greenhouse.io", "greenhouse"),
    ("lever.co", "lever"),
    ("ashbyhq.com", "ashby"),
    ("myworkdayjobs.com", "workday"),
    ("workday.com", "workday"),
]

_ADAPTERS: dict[str, type[Adapter]] = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
    "ashby": AshbyAdapter,
    "workday": WorkdayAdapter,
    "generic": GenericAdapter,
}


def detect_ats(url: str) -> str:
    """Classify an application URL into an ATS name. Falls back to 'generic'."""
    host = (urlparse(url).hostname or "").lower()
    if not host:
        # No scheme? Try matching against the raw string as a last resort.
        host = url.lower()
    for needle, ats in _HOST_PATTERNS:
        if needle in host:
            return ats
    return "generic"


def get_adapter(url: str) -> Adapter:
    return _ADAPTERS[detect_ats(url)]()
