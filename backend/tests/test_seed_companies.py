import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from app.db import Base
from app.models.company import AtsType, Company
from seed_companies import load_companies, upsert_company, EXAMPLE_PATH


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_load_companies_from_example_file():
    entries = load_companies(EXAMPLE_PATH)
    assert len(entries) >= 10
    assert all("name" in e and "ats_type" in e for e in entries)


def test_upsert_company_creates_new():
    session = _session()
    entry = {"name": "Stripe", "ats_type": "greenhouse", "ats_board_id": "stripe", "is_target": True}

    company, created = upsert_company(session, entry)
    session.commit()

    assert created is True
    assert company.ats_type == AtsType.greenhouse
    assert company.ats_board_id == "stripe"
    assert company.is_target is True


def test_upsert_company_updates_existing_case_insensitive():
    session = _session()
    session.add(Company(name="stripe", ats_type=AtsType.unknown))
    session.commit()

    entry = {"name": "Stripe", "ats_type": "greenhouse", "ats_board_id": "stripe", "is_target": True}
    company, created = upsert_company(session, entry)
    session.commit()

    assert created is False
    assert session.query(Company).count() == 1
    assert company.ats_type == AtsType.greenhouse


def test_seed_example_file_end_to_end():
    session = _session()
    entries = load_companies(EXAMPLE_PATH)

    for entry in entries:
        upsert_company(session, entry)
    session.commit()

    assert session.query(Company).count() == len(entries)
    stripe = session.query(Company).filter(Company.name == "Stripe").one()
    assert stripe.ats_type == AtsType.greenhouse
