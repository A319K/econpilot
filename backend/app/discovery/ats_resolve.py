"""Resolve an application URL to (AtsType, board_id).

The discovery sources key off Company.ats_board_id and hit these APIs:
  Greenhouse: boards-api.greenhouse.io/v1/boards/<board_id>/jobs
  Lever:      api.lever.co/v0/postings/<board_id>
  Ashby:      api.ashbyhq.com/posting-api/job-board/<board_id>
so the board_id extracted here must equal the org slug those APIs expect --
which is exactly the first path segment (or the ?for= param for Greenhouse
embed links) of a public application URL.

Workday is scanned via its keyless CXS JSON API, which is keyed by the full host
(tenant.dc.myworkdayjobs.com) plus the job-board *site* (the first path segment).
Neither alone is enough, so we encode both into the board_id as "host|site"; the
WorkdaySource splits it back apart. Public URL shape:
  https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US/Intern_JR1
A locale prefix ("/en-US/") may sit before the site segment and is skipped.
Companies we can't classify stay unknown and are simply not auto-scanned.
"""

import re
from urllib.parse import parse_qs, urlparse

from app.models.company import AtsType

# Workday URLs may carry a locale segment (e.g. "en-US") before the job-board
# site; skip it so the real site name is used as the board id.
_LOCALE_RE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")


def resolve_ats(url: str | None) -> tuple[AtsType, str | None]:
    """Best-effort (AtsType, board_id) from an application URL. Returns
    (AtsType.unknown, None) when the host isn't a recognized ATS."""
    if not url:
        return AtsType.unknown, None

    # Tolerate scheme-less URLs ("jobs.lever.co/acme") so parsing still yields a
    # host rather than dumping everything into the path.
    parsed = urlparse(url if "//" in url else f"//{url}", scheme="https")
    host = (parsed.hostname or "").lower()
    segments = [s for s in parsed.path.split("/") if s]

    if "greenhouse.io" in host:
        # Embed links carry the board id in ?for=, not the path.
        if segments and segments[0] == "embed":
            for_vals = parse_qs(parsed.query).get("for")
            return AtsType.greenhouse, (for_vals[0] if for_vals else None)
        return AtsType.greenhouse, (segments[0] if segments else None)

    if "lever.co" in host:
        return AtsType.lever, (segments[0] if segments else None)

    if "ashbyhq.com" in host:
        return AtsType.ashby, (segments[0] if segments else None)

    if "myworkdayjobs.com" in host or "workday.com" in host:
        site_segments = segments[1:] if segments and _LOCALE_RE.match(segments[0]) else segments
        if host and site_segments:
            return AtsType.workday, f"{host}|{site_segments[0]}"
        return AtsType.workday, None

    return AtsType.unknown, None
