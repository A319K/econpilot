"""Upsert companies from companies.yaml (or companies.example.yaml) into the DB.

Usage (run from backend/):
    .venv/bin/python scripts/seed_companies.py [path/to/companies.yaml]
"""

import sys
import warnings
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.models.company import AtsType, Company  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PATH = REPO_ROOT / "companies.yaml"
EXAMPLE_PATH = REPO_ROOT / "companies.example.yaml"


def load_companies(path: Path) -> list[dict]:
    if not path.exists():
        warnings.warn(f"{path} not found; falling back to {EXAMPLE_PATH}", stacklevel=2)
        path = EXAMPLE_PATH

    with path.open("r") as f:
        data = yaml.safe_load(f)

    return data.get("companies", [])


def upsert_company(db, entry: dict) -> tuple[Company, bool]:
    name = entry["name"]
    existing = db.query(Company).filter(Company.name.ilike(name)).one_or_none()

    ats_type = AtsType(entry.get("ats_type", "unknown"))
    fields = {
        "ats_type": ats_type,
        "ats_board_id": entry.get("ats_board_id"),
        "careers_url": entry.get("careers_url"),
        "is_target": entry.get("is_target", False),
    }

    if existing is None:
        company = Company(name=name, **fields)
        db.add(company)
        db.flush()
        return company, True

    for field, value in fields.items():
        setattr(existing, field, value)
    return existing, False


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    entries = load_companies(path)

    db = SessionLocal()
    created, updated = 0, 0
    try:
        for entry in entries:
            _, was_created = upsert_company(db, entry)
            if was_created:
                created += 1
            else:
                updated += 1
        db.commit()
    finally:
        db.close()

    print(f"Seeded companies: {created} created, {updated} updated ({len(entries)} total).")


if __name__ == "__main__":
    main()
