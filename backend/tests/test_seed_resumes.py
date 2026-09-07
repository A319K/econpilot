import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from app.db import Base
from app.materials.regions import parse_regions
from app.models.job import JobFamily
from app.models.resume_version import ResumeVersion
from seed_resumes import TEMPLATES, TEMPLATES_DIR, upsert_resume


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_all_templates_exist_on_disk():
    for filename in TEMPLATES:
        assert (TEMPLATES_DIR / f"{filename}.tex").exists()


def test_all_templates_have_summary_and_skills_regions():
    for filename in TEMPLATES:
        source = (TEMPLATES_DIR / f"{filename}.tex").read_text()
        regions = parse_regions(source)
        assert "summary" in regions
        assert "skills" in regions


def test_upsert_resume_creates_new_base_template(monkeypatch):
    import seed_resumes

    monkeypatch.setattr(seed_resumes, "compile_pdf", lambda source, name: "/fake/output.pdf")

    session = _session()
    resume, created = upsert_resume(session, "consulting", "Consulting Base", JobFamily.consulting)

    assert created is True
    assert resume.is_base_template is True
    assert resume.job_family == JobFamily.consulting
    assert resume.pdf_path == "/fake/output.pdf"


def test_upsert_resume_updates_existing_by_name(monkeypatch):
    import seed_resumes

    monkeypatch.setattr(seed_resumes, "compile_pdf", lambda source, name: "/fake/output.pdf")

    session = _session()
    upsert_resume(session, "consulting", "Consulting Base", JobFamily.consulting)
    session.commit()

    resume, created = upsert_resume(session, "consulting", "Consulting Base", JobFamily.consulting)
    session.commit()

    assert created is False
    assert session.query(ResumeVersion).count() == 1
