"""Phase B: month-bucket derivation, historical refresh (creates + resolves
companies), and the next-month pre-activation."""

import json
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.discovery import seasonality
from app.discovery.seasonality import (
    activate_expected_companies,
    compute_month_buckets,
    refresh_expected_months,
)
from app.models.company import AtsType, Company


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _row(company, url, month):
    return {
        "company_name": company,
        "title": "Intern",
        "location": None,
        "url": url,
        "posted_at": datetime(2025, month, 15, tzinfo=timezone.utc),
    }


def test_compute_month_buckets_unions_months_per_company():
    rows = [
        _row("Acme", "https://boards.greenhouse.io/acme/1", 1),
        _row("Acme", "https://boards.greenhouse.io/acme/2", 3),
        _row("Beta", "https://jobs.lever.co/beta/1", 9),
    ]
    buckets = compute_month_buckets(rows)
    assert buckets["Acme"]["months"] == [1, 3]
    assert buckets["Beta"]["months"] == [9]
    assert "greenhouse.io/acme" in buckets["Acme"]["url"]


def test_compute_month_buckets_skips_rows_without_date():
    rows = [{"company_name": "X", "url": "u", "posted_at": None}]
    assert compute_month_buckets(rows) == {}


_SAMPLE = [
    {"company_name": "Acme", "title": "Intern", "url": "https://boards.greenhouse.io/acme/1",
     "locations": [], "date_posted": int(datetime(2025, 1, 5, tzinfo=timezone.utc).timestamp()),
     "active": False},
    {"company_name": "Acme", "title": "Intern", "url": "https://boards.greenhouse.io/acme/2",
     "locations": [], "date_posted": int(datetime(2025, 2, 5, tzinfo=timezone.utc).timestamp()),
     "active": True},
    {"company_name": "Beta", "title": "Intern", "url": "https://jobs.lever.co/beta/1",
     "locations": [], "date_posted": int(datetime(2025, 9, 5, tzinfo=timezone.utc).timestamp()),
     "active": False},
]


def _mock_fetch(monkeypatch, records):
    from app.discovery.sources.github_repo import parse_listings_json

    async def fake_fetch_all(active_only=True):
        return parse_listings_json(json.dumps(records), active_only=active_only)

    monkeypatch.setattr(seasonality, "fetch_all_rows", fake_fetch_all)


@pytest.mark.asyncio
async def test_refresh_creates_and_resolves_companies(monkeypatch):
    db = _session()
    _mock_fetch(monkeypatch, _SAMPLE)

    summary = await refresh_expected_months(db)

    assert summary.companies_seen == 2
    assert summary.companies_created == 2

    acme = db.query(Company).filter(Company.name == "Acme").one()
    assert acme.expected_months == [1, 2]  # unioned across active + closed
    assert acme.ats_type == AtsType.greenhouse
    assert acme.ats_board_id == "acme"

    beta = db.query(Company).filter(Company.name == "Beta").one()
    assert beta.expected_months == [9]
    assert beta.ats_type == AtsType.lever


@pytest.mark.asyncio
async def test_refresh_is_idempotent_and_merges(monkeypatch):
    db = _session()
    # Pre-existing company already has one month recorded.
    db.add(Company(name="Acme", ats_type=AtsType.greenhouse, ats_board_id="acme",
                   expected_months=[11]))
    db.commit()
    _mock_fetch(monkeypatch, _SAMPLE)

    await refresh_expected_months(db)

    acme = db.query(Company).filter(Company.name == "Acme").one()
    assert acme.expected_months == [1, 2, 11]  # merged, not reset


def test_activate_targets_companies_expected_next_month():
    db = _session()
    db.add_all([
        Company(name="Jan Co", ats_type=AtsType.greenhouse, ats_board_id="jan",
                expected_months=[1], is_target=False),
        Company(name="Feb Co", ats_type=AtsType.greenhouse, ats_board_id="feb",
                expected_months=[2], is_target=False),
        Company(name="Already", ats_type=AtsType.greenhouse, ats_board_id="al",
                expected_months=[2], is_target=True),
    ])
    db.commit()

    # In January, we pre-activate everyone expected in February.
    result = activate_expected_companies(db, current_month=1)

    assert result.target_month == 2
    assert result.activated == 1  # Feb Co
    assert result.already_active == 1  # Already
    assert db.query(Company).filter(Company.name == "Feb Co").one().is_target is True
    assert db.query(Company).filter(Company.name == "Jan Co").one().is_target is False


def test_activate_wraps_december_to_january():
    db = _session()
    db.add(Company(name="Jan Co", ats_type=AtsType.greenhouse, ats_board_id="jan",
                   expected_months=[1], is_target=False))
    db.commit()

    result = activate_expected_companies(db, current_month=12)

    assert result.target_month == 1
    assert result.activated == 1


def test_activate_never_deactivates():
    db = _session()
    # A target whose expected month is NOT next month must stay a target.
    db.add(Company(name="Keep", ats_type=AtsType.greenhouse, ats_board_id="k",
                   expected_months=[6], is_target=True))
    db.commit()

    activate_expected_companies(db, current_month=1)

    assert db.query(Company).filter(Company.name == "Keep").one().is_target is True
