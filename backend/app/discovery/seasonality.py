"""Phase B: seasonal corpus + pre-activation.

Internship postings are strongly seasonal (the SimplifyJobs feed clusters
Dec-Mar and tapers through summer). We derive, per company, the calendar months
it has historically opened internships from the full dated listings history,
then a monthly cron (activate_expected_companies) flips companies expected to
post *next* month into active watch targets -- so the watcher is already
scanning them the moment a role opens, instead of finding it days later.

The historical read uses active_only=False (the whole dated history, not just
currently-open roles) and reuses the pipeline's company upsert + ATS resolution
so a company known only from a past season still becomes directly scannable.
"""

import logging

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.discovery.pipeline import (
    find_company,
    get_or_create_company,
    maybe_resolve_company_ats,
)
from app.discovery.sources.github_repo import fetch_all_rows
from app.models.company import Company

logger = logging.getLogger(__name__)


class SeasonalityRefresh(BaseModel):
    companies_seen: int = 0
    companies_created: int = 0
    companies_updated: int = 0
    ats_resolved: int = 0


class PreActivation(BaseModel):
    target_month: int
    activated: int = 0
    already_active: int = 0


def compute_month_buckets(rows: list[dict]) -> dict[str, dict]:
    """Aggregate parse_listings_json rows into
    company_name -> {"months": sorted[int], "url": sample application url}.

    The sample url is any of the company's postings; it's only used to resolve
    the company's ATS, which is org-wide, so the specific posting doesn't matter.
    """
    buckets: dict[str, dict] = {}
    for row in rows:
        posted = row.get("posted_at")
        name = (row.get("company_name") or "").strip()
        if not posted or not name:
            continue
        entry = buckets.setdefault(name, {"months": set(), "url": row.get("url")})
        entry["months"].add(posted.month)
        if not entry["url"]:
            entry["url"] = row.get("url")
    return {
        name: {"months": sorted(entry["months"]), "url": entry["url"]}
        for name, entry in buckets.items()
    }


async def refresh_expected_months(db: Session) -> SeasonalityRefresh:
    """Rebuild each company's expected_months from the full dated listings feed,
    creating companies seen only in past seasons and resolving their ATS so they
    can be scanned before they repost. Idempotent: months are merged, not reset,
    so a company's history only grows."""
    rows = await fetch_all_rows(active_only=False)
    buckets = compute_month_buckets(rows)

    summary = SeasonalityRefresh(companies_seen=len(buckets))
    for name, info in buckets.items():
        existing = find_company(db, name)
        company = existing if existing is not None else get_or_create_company(db, name)
        if existing is None:
            summary.companies_created += 1
        if maybe_resolve_company_ats(company, info["url"]):
            summary.ats_resolved += 1

        merged = sorted(set(company.expected_months or []) | set(info["months"]))
        if merged != (company.expected_months or []):
            company.expected_months = merged
            summary.companies_updated += 1

    db.commit()
    logger.info(
        "seasonality refresh: %d seen, %d created, %d updated, %d ATS-resolved",
        summary.companies_seen,
        summary.companies_created,
        summary.companies_updated,
        summary.ats_resolved,
    )
    return summary


def _next_month(current_month: int) -> int:
    return current_month % 12 + 1


def activate_expected_companies(db: Session, current_month: int) -> PreActivation:
    """Flip is_target=True for every company whose expected_months includes the
    month *after* current_month. Never deactivates anyone -- once a company is a
    target it stays one (the user asked to keep the old ones accumulating)."""
    target_month = _next_month(current_month)
    result = PreActivation(target_month=target_month)

    companies = (
        db.query(Company).filter(Company.expected_months.isnot(None)).all()
    )
    for company in companies:
        if target_month not in (company.expected_months or []):
            continue
        if company.is_target:
            result.already_active += 1
            continue
        company.is_target = True
        result.activated += 1

    db.commit()
    logger.info(
        "pre-activation for month %d: %d activated, %d already active",
        target_month,
        result.activated,
        result.already_active,
    )
    return result
