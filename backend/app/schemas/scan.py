from pydantic import BaseModel

from app.discovery.scan import ScanReport


class ScanRequest(BaseModel):
    role_type: str = "all"
    targets_only: bool = False
    # Override the configured freshness window (days). None uses the default
    # (settings.scan_max_age_days); 0 disables the cutoff for this scan.
    max_age_days: int | None = None


__all__ = ["ScanRequest", "ScanReport"]
