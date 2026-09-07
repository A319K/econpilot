from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.application import Application
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.models.resume_version import ResumeVersion

client = TestClient(app)


def _patch_compile(monkeypatch, path="/fake/output.pdf"):
    from app.routers import resumes as resumes_router_module

    monkeypatch.setattr(resumes_router_module, "compile_pdf", lambda source, name: path)


def test_create_resume_compiles_and_persists(monkeypatch):
    _patch_compile(monkeypatch)

    response = client.post(
        "/resumes",
        json={
            "name": "SWE Base",
            "job_family": "swe",
            "latex_source": "\\documentclass{article}\\begin{document}x\\end{document}",
            "keywords": ["python"],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["is_base_template"] is True
    assert body["pdf_path"] == "/fake/output.pdf"


def test_create_resume_returns_422_on_latex_error(monkeypatch):
    from app.materials.latex import LatexError
    from app.routers import resumes as resumes_router_module

    def fail(*args, **kwargs):
        raise LatexError("bad latex")

    monkeypatch.setattr(resumes_router_module, "compile_pdf", fail)

    response = client.post(
        "/resumes",
        json={"name": "Bad", "job_family": "swe", "latex_source": "\\bad{", "keywords": []},
    )
    assert response.status_code == 422


def test_get_resume_not_found():
    response = client.get("/resumes/999999")
    assert response.status_code == 404


def test_list_and_get_resume(monkeypatch):
    _patch_compile(monkeypatch)

    create_resp = client.post(
        "/resumes",
        json={"name": "Data Base", "job_family": "data", "latex_source": "\\documentclass{article}\\begin{document}x\\end{document}"},
    )
    resume_id = create_resp.json()["id"]

    list_resp = client.get("/resumes")
    assert list_resp.status_code == 200
    assert any(r["id"] == resume_id for r in list_resp.json())

    get_resp = client.get(f"/resumes/{resume_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == resume_id


def test_update_resume_recompiles_only_when_source_changes(monkeypatch):
    _patch_compile(monkeypatch, path="/fake/v1.pdf")

    create_resp = client.post(
        "/resumes",
        json={"name": "ML Base", "job_family": "ml", "latex_source": "\\documentclass{article}\\begin{document}x\\end{document}"},
    )
    resume_id = create_resp.json()["id"]
    assert create_resp.json()["pdf_path"] == "/fake/v1.pdf"

    # Update a non-source field; pdf_path should be unchanged.
    rename_resp = client.put(f"/resumes/{resume_id}", json={"name": "ML Base Renamed"})
    assert rename_resp.status_code == 200
    assert rename_resp.json()["pdf_path"] == "/fake/v1.pdf"
    assert rename_resp.json()["name"] == "ML Base Renamed"

    _patch_compile(monkeypatch, path="/fake/v2.pdf")
    source_resp = client.put(
        f"/resumes/{resume_id}",
        json={"latex_source": "\\documentclass{article}\\begin{document}y\\end{document}"},
    )
    assert source_resp.status_code == 200
    assert source_resp.json()["pdf_path"] == "/fake/v2.pdf"


def test_delete_resume_succeeds_when_unreferenced(monkeypatch):
    _patch_compile(monkeypatch)

    create_resp = client.post(
        "/resumes",
        json={"name": "Cloud Base", "job_family": "cloud_infra", "latex_source": "\\documentclass{article}\\begin{document}x\\end{document}"},
    )
    resume_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/resumes/{resume_id}")
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/resumes/{resume_id}")
    assert get_resp.status_code == 404


def test_delete_resume_blocked_when_referenced_by_application(monkeypatch):
    _patch_compile(monkeypatch)

    create_resp = client.post(
        "/resumes",
        json={"name": "Referenced Base", "job_family": "swe", "latex_source": "\\documentclass{article}\\begin{document}x\\end{document}"},
    )
    resume_id = create_resp.json()["id"]

    db = SessionLocal()
    try:
        company = Company(name="RefCo")
        db.add(company)
        db.commit()
        job = Job(
            company_id=company.id,
            title="SWE Intern",
            url="https://example.com/ref-job",
            source=JobSource.manual,
            role_type=RoleType.internship,
            job_family=JobFamily.swe,
            dedup_hash="refhash",
        )
        db.add(job)
        db.commit()
        application = Application(job_id=job.id, resume_version_id=resume_id)
        db.add(application)
        db.commit()
    finally:
        db.close()

    delete_resp = client.delete(f"/resumes/{resume_id}")
    assert delete_resp.status_code == 409
