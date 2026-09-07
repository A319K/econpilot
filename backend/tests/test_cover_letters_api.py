from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.application import Application
from app.models.company import Company
from app.models.cover_letter import CoverLetter
from app.models.job import Job, JobFamily, JobSource, RoleType

client = TestClient(app)


def _make_cover_letter() -> int:
    db = SessionLocal()
    try:
        company = Company(name="CLCo")
        db.add(company)
        db.commit()
        job = Job(
            company_id=company.id,
            title="SWE Intern",
            url=f"https://example.com/cl-job-{company.id}",
            source=JobSource.manual,
            role_type=RoleType.internship,
            job_family=JobFamily.swe,
            dedup_hash=f"clhash{company.id}",
        )
        db.add(job)
        db.commit()
        application = Application(job_id=job.id)
        db.add(application)
        db.commit()
        cover_letter = CoverLetter(application_id=application.id, content="Original body.", needs_review=True)
        db.add(cover_letter)
        db.commit()
        return cover_letter.id
    finally:
        db.close()


def test_get_cover_letter_not_found():
    response = client.get("/cover-letters/999999")
    assert response.status_code == 404


def test_get_cover_letter():
    cl_id = _make_cover_letter()
    response = client.get(f"/cover-letters/{cl_id}")
    assert response.status_code == 200
    assert response.json()["content"] == "Original body."


def test_put_cover_letter_recompiles_and_keeps_needs_review_true(monkeypatch):
    from app.routers import cover_letters as cover_letters_router_module

    monkeypatch.setattr(
        cover_letters_router_module, "compile_cover_letter", lambda content, company, job_id: "/fake/cl.pdf"
    )

    cl_id = _make_cover_letter()
    response = client.put(f"/cover-letters/{cl_id}", json={"content": "Edited body."})

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "Edited body."
    assert body["pdf_path"] == "/fake/cl.pdf"
    assert body["needs_review"] is True


def test_patch_cover_letter_marks_reviewed():
    cl_id = _make_cover_letter()

    response = client.patch(f"/cover-letters/{cl_id}", json={"reviewed": True})
    assert response.status_code == 200
    assert response.json()["needs_review"] is False


def test_patch_cover_letter_can_unmark_reviewed():
    cl_id = _make_cover_letter()

    client.patch(f"/cover-letters/{cl_id}", json={"reviewed": True})
    response = client.patch(f"/cover-letters/{cl_id}", json={"reviewed": False})
    assert response.json()["needs_review"] is True


def test_put_cover_letter_not_found(monkeypatch):
    response = client.put("/cover-letters/999999", json={"content": "x"})
    assert response.status_code == 404
