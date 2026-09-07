from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.materials import cover_letter as cover_letter_module
from app.materials import keywords as keywords_module
from app.materials import tailoring as tailoring_module
from app.models.application import Application
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.models.resume_version import ResumeVersion

client = TestClient(app)

BASE_SOURCE = """\\documentclass{article}
\\begin{document}
%% TAILOR-BEGIN:summary
Original summary.
%% TAILOR-END:summary
\\end{document}
"""


def _make_job_with_base_resume(description="We need a Python engineer."):
    db = SessionLocal()
    try:
        company = Company(name="PrepCo")
        db.add(company)
        db.commit()
        job = Job(
            company_id=company.id,
            title="Software Engineer Intern",
            url=f"https://example.com/prep-job-{company.id}",
            source=JobSource.manual,
            role_type=RoleType.internship,
            job_family=JobFamily.consulting,
            description=description,
            dedup_hash=f"prephash{company.id}",
        )
        db.add(job)
        db.commit()
        resume = ResumeVersion(
            name="SWE Base",
            job_family=JobFamily.consulting,
            latex_source=BASE_SOURCE,
            is_base_template=True,
            pdf_path="/fake/base.pdf",
        )
        db.add(resume)
        db.commit()
        return job.id
    finally:
        db.close()


def _mock_llm(monkeypatch):
    async def fake_complete_json(system, user, schema_hint, **kwargs):
        return {"skills": ["Python"], "responsibilities": [], "qualifications": [], "nice_to_have": []}

    async def fake_complete(system, user, **kwargs):
        return "Tailored or cover letter text." if True else None

    monkeypatch.setattr(keywords_module, "complete_json", fake_complete_json)
    monkeypatch.setattr(tailoring_module, "complete", fake_complete)
    monkeypatch.setattr(cover_letter_module, "complete", fake_complete)
    monkeypatch.setattr(tailoring_module, "compile_pdf", lambda source, name: "/fake/resume.pdf")
    monkeypatch.setattr(
        cover_letter_module, "compile_cover_letter", lambda content, company, job_id: "/fake/cl.pdf"
    )


def test_prepare_job_materials_not_found():
    response = client.post("/jobs/999999/prepare", json={})
    assert response.status_code == 404


def test_prepare_job_materials_full_flow(monkeypatch):
    # Explicit tailor=True exercises the per-job rewrite path (no longer the
    # default - see test_prepare_defaults_to_select_only).
    job_id = _make_job_with_base_resume()
    _mock_llm(monkeypatch)

    response = client.post(f"/jobs/{job_id}/prepare", json={"tailor": True})
    assert response.status_code == 200
    body = response.json()

    assert body["tailored"] is True
    assert body["cover_letter_id"] is not None
    assert "resume" in body["pdf_paths"]
    assert "cover_letter" in body["pdf_paths"]

    db = SessionLocal()
    try:
        application = db.query(Application).filter(Application.job_id == job_id).one()
        assert application.resume_version_id == body["resume_used"]
        assert application.cover_letter_id == body["cover_letter_id"]
    finally:
        db.close()


def test_prepare_defaults_to_select_only(monkeypatch):
    # With no `tailor` in the payload, Prepare uses the configured default
    # (prepare_tailor_default=False): it selects the best-fit base resume and
    # reuses its already-compiled PDF instead of rewriting a per-job one.
    job_id = _make_job_with_base_resume()
    _mock_llm(monkeypatch)

    response = client.post(f"/jobs/{job_id}/prepare", json={})
    assert response.status_code == 200
    body = response.json()

    assert body["tailored"] is False
    # The attached resume is the base template, reusing its compiled PDF.
    assert body["pdf_paths"].get("resume") == "/fake/base.pdf"
    # Cover letter is still per-job unless explicitly disabled.
    assert body["cover_letter_id"] is not None

    db = SessionLocal()
    try:
        used = db.get(ResumeVersion, body["resume_used"])
        # The resume attached is an unmodified base template, not a tailored clone.
        assert used.is_base_template is True
    finally:
        db.close()


def test_prepare_job_materials_respects_flags(monkeypatch):
    job_id = _make_job_with_base_resume()
    _mock_llm(monkeypatch)

    response = client.post(f"/jobs/{job_id}/prepare", json={"tailor": False, "cover_letter": False})
    assert response.status_code == 200
    body = response.json()

    assert body["tailored"] is False
    assert body["cover_letter_id"] is None
