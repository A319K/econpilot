"""Upsert the placeholder base resume templates from templates/resumes/ into
the DB, compiling each to a PDF.

These are stand-ins -- replace latex_source with your real resumes later via
the ResumeVersion API (PUT /resumes/{id}), or add more via POST /resumes.

Usage (run from backend/):
    .venv/bin/python scripts/seed_resumes.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.materials.latex import LatexError, build_output_name, compile_pdf  # noqa: E402
from app.models.job import JobFamily  # noqa: E402
from app.models.resume_version import ResumeVersion  # noqa: E402

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "resumes"

# filename (without .tex) -> (display name, job_family)
TEMPLATES = {
    "swe": ("Software Engineering Base", JobFamily.swe),
    "data": ("Data Base", JobFamily.data),
    "cloud_infra": ("Cloud/Infra Base", JobFamily.cloud_infra),
}


def upsert_resume(db, filename: str, name: str, job_family: JobFamily) -> tuple[ResumeVersion, bool]:
    latex_source = (TEMPLATES_DIR / f"{filename}.tex").read_text()

    existing = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.name == name, ResumeVersion.is_base_template.is_(True))
        .one_or_none()
    )

    if existing is None:
        resume = ResumeVersion(name=name, job_family=job_family, latex_source=latex_source, is_base_template=True)
        db.add(resume)
        db.flush()
        created = True
    else:
        existing.latex_source = latex_source
        existing.job_family = job_family
        resume = existing
        created = False

    output_name = build_output_name(name, resume.id, "resume")
    resume.pdf_path = str(compile_pdf(latex_source, output_name))
    return resume, created


def main() -> None:
    db = SessionLocal()
    created, updated, failed = 0, 0, 0
    try:
        for filename, (name, job_family) in TEMPLATES.items():
            try:
                _, was_created = upsert_resume(db, filename, name, job_family)
                db.commit()
                if was_created:
                    created += 1
                else:
                    updated += 1
            except LatexError as exc:
                db.rollback()
                failed += 1
                print(f"Failed to compile {filename}: {exc}")
    finally:
        db.close()

    print(f"Seeded resumes: {created} created, {updated} updated, {failed} failed ({len(TEMPLATES)} total).")


if __name__ == "__main__":
    main()
