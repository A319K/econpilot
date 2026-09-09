"""Active company-name -> ATS resolution.

`ats_resolve` classifies a company *passively* from a job's application URL. That
misses any company we know by name but never saw a resolvable URL for -- which
is how big names (Datadog, Palantir, Databricks, ...) ended up `unknown` and
therefore silently skipped by every scan.

This module resolves those companies *actively*: it derives candidate org slugs
from the company name and probes the keyless Greenhouse/Lever/Ashby list APIs
(the same endpoints the sources fetch from). A slug that returns a valid board
payload is accepted even when it currently has no open jobs.

Workday is deliberately out of scope: its coordinate is an opaque tenant host
plus site that cannot be derived from a company name, so those stay unknown.
"""

import asyncio
import random
import re
from datetime import timedelta

import httpx
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.company import AtsType, Company
from app.models.mixins import utcnow

_PROBE_TIMEOUT_SECONDS = 12.0
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
# Corporate suffixes that never appear in an ATS org slug.
_SUFFIX_RE = re.compile(
    r"\b(inc|corp|corporation|company|co|technologies|technology|labs|systems|"
    r"group|holdings|international|llc|ltd|plc)\b"
)


class ProbeIncompleteError(RuntimeError):
    """A board lookup could not distinguish a miss from a transient failure."""


def slug_candidates(name: str) -> list[str]:
    """Ordered, de-duplicated slug guesses for a company name, most-specific
    first. Emoji/punctuation are stripped; a suffix-trimmed variant is added so
    e.g. 'Acme Technologies' also tries 'acme'."""
    base = re.sub(r"[^\w\s-]", " ", name).lower()
    base = re.sub(r"\s+", " ", base).strip()
    if not base:
        return []

    variants = [base.replace(" ", ""), base.replace(" ", "-")]
    trimmed = _SUFFIX_RE.sub("", base).strip()
    trimmed = re.sub(r"\s+", " ", trimmed)
    if trimmed and trimmed != base:
        variants += [trimmed.replace(" ", ""), trimmed.replace(" ", "-")]

    out: list[str] = []
    for v in variants:
        # Guard against absurdly short/generic slugs that collide with unrelated
        # boards (e.g. a 2-char slug). Real org slugs are longer.
        if len(v) >= 3 and v not in out:
            out.append(v)
    return out


async def _hit(client: httpx.AsyncClient, slug: str) -> tuple[AtsType, str] | None:
    """Return (ats_type, slug) if ``slug`` names a valid public ATS board."""
    incomplete: list[str] = []
    try:
        r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
        if r.status_code == 200:
            body = r.json()
            if isinstance(body, dict) and isinstance(body.get("jobs"), list):
                return AtsType.greenhouse, slug
            incomplete.append("Greenhouse returned an unexpected response")
        if r.status_code not in (200, 404):
            incomplete.append(f"Greenhouse returned HTTP {r.status_code}")
    except (httpx.HTTPError, ValueError) as exc:
        incomplete.append(f"Greenhouse: {exc}")
    try:
        r = await client.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
        if r.status_code == 200:
            body = r.json()
            if isinstance(body, list):
                return AtsType.lever, slug
            incomplete.append("Lever returned an unexpected response")
        if r.status_code not in (200, 404):
            incomplete.append(f"Lever returned HTTP {r.status_code}")
    except (httpx.HTTPError, ValueError) as exc:
        incomplete.append(f"Lever: {exc}")
    try:
        r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
        if r.status_code == 200:
            body = r.json()
            if isinstance(body, dict) and isinstance(body.get("jobs"), list):
                return AtsType.ashby, slug
            incomplete.append("Ashby returned an unexpected response")
        if r.status_code not in (200, 404):
            incomplete.append(f"Ashby returned HTTP {r.status_code}")
    except (httpx.HTTPError, ValueError) as exc:
        incomplete.append(f"Ashby: {exc}")
    if incomplete:
        raise ProbeIncompleteError("; ".join(incomplete))
    return None


async def probe_company_ats(
    client: httpx.AsyncClient, name: str
) -> tuple[AtsType, str] | None:
    """Best-effort (ats_type, board_id) for a company name, or None."""
    incomplete: list[str] = []
    for slug in slug_candidates(name):
        try:
            found = await _hit(client, slug)
        except ProbeIncompleteError as exc:
            incomplete.append(f"{slug}: {exc}")
            continue
        if found:
            return found
    if incomplete:
        raise ProbeIncompleteError(" | ".join(incomplete))
    return None


def _companies_to_probe(db: Session, reprobe_after_days: int, limit: int | None) -> list[Company]:
    """Unknown-ATS companies never probed, or last probed longer than
    `reprobe_after_days` ago (so a company that later adopts a supported ATS is
    eventually picked up without re-probing dead names every scan)."""
    stale_before = utcnow() - timedelta(days=reprobe_after_days)
    query = (
        db.query(Company)
        .filter(Company.ats_type == AtsType.unknown)
        .filter(or_(Company.ats_probed_at.is_(None), Company.ats_probed_at < stale_before))
        .order_by(Company.is_target.desc(), Company.id)
    )
    if limit is not None:
        query = query.limit(limit)
    return query.all()


async def resolve_unknown_companies(
    db: Session,
    reprobe_after_days: int = 30,
    concurrency: int = 8,
    limit: int | None = None,
) -> dict[str, int | list[str]]:
    """Actively resolve unknown-ATS companies by probing their name against the
    keyless job-board APIs, persisting any hit. Returns a summary dict. Every
    probed company gets `ats_probed_at` stamped (hit or miss) so scans don't
    re-probe it until the reprobe window elapses."""
    companies = _companies_to_probe(db, reprobe_after_days, limit)
    summary: dict[str, int | list[str]] = {
        "probed": 0,
        "resolved": 0,
        "resolved_names": [],
        "errors": [],
    }
    if not companies:
        return summary

    semaphore = asyncio.Semaphore(concurrency)
    now = utcnow()

    async def worker(client: httpx.AsyncClient, company: Company):
        async with semaphore:
            await asyncio.sleep(random.uniform(0, 0.25))  # jitter: don't burst the APIs
            try:
                return company, await probe_company_ats(client, company.name), None
            except ProbeIncompleteError as exc:
                return company, None, str(exc)

    async with httpx.AsyncClient(
        timeout=_PROBE_TIMEOUT_SECONDS, headers={"User-Agent": _USER_AGENT}
    ) as client:
        results = await asyncio.gather(*[worker(client, c) for c in companies])

    resolved_names: list[str] = []
    errors: list[str] = []
    for company, found, error in results:
        if error is not None:
            errors.append(
                f"{company.name}: could not finish checking job boards; will retry later"
            )
            continue
        company.ats_probed_at = now
        summary["probed"] = int(summary["probed"]) + 1
        if found is None:
            continue
        ats_type, board_id = found
        company.ats_type = ats_type
        company.ats_board_id = board_id
        summary["resolved"] = int(summary["resolved"]) + 1
        resolved_names.append(f"{company.name} -> {ats_type.value}/{board_id}")

    db.commit()
    summary["resolved_names"] = resolved_names
    summary["errors"] = errors
    return summary
