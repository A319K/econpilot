from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.application import Application, ApplicationStatus
from app.models.company import Company
from app.models.cover_letter import CoverLetter
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.models.resume_version import ResumeVersion

client = TestClient(app)

_counter = {"n": 0}


def _next_n() -> int:
    _counter["n"] += 1
    return _counter["n"]


def _setup_application(
    role_type=RoleType.internship,
    status=ApplicationStatus.discovered,
    with_cover_letter=False,
    with_resume=False,
    company_name=None,
) -> dict:
    n = _next_n()
    db = SessionLocal()
    try:
        company = Company(name=company_name or f"AppCo{n}")
        db.add(company)
        db.commit()

        job = Job(
            company_id=company.id,
            title=f"SWE Intern {n}",
            url=f"https://example.com/app-job-{n}",
            source=JobSource.manual,
            role_type=role_type,
            job_family=JobFamily.consulting,
            dedup_hash=f"apphash{n}",
            score=42.0,
        )
        db.add(job)
        db.commit()

        application = Application(job_id=job.id, status=status)
        db.add(application)
        db.commit()

        if with_resume:
            # Represents a resume already attached to this application (e.g.
            # a tailored variant), not a candidate template up for
            # selection - must stay out of the base-template pool so it
            # doesn't affect resume selection in other tests sharing this DB.
            resume = ResumeVersion(
                name="Attached Resume",
                job_family=JobFamily.consulting,
                latex_source="\\documentclass{article}\\begin{document}x\\end{document}",
                is_base_template=False,
                pdf_path="/fake/resume.pdf",
            )
            db.add(resume)
            db.commit()
            application.resume_version_id = resume.id
            db.commit()

        if with_cover_letter:
            cl = CoverLetter(application_id=application.id, content="Body.", needs_review=True)
            db.add(cl)
            db.commit()
            application.cover_letter_id = cl.id
            db.commit()

        return {"application_id": application.id, "job_id": job.id, "company_id": company.id}
    finally:
        db.close()


def test_list_applications_embeds_job_summary():
    ctx = _setup_application()

    response = client.get("/applications")
    assert response.status_code == 200
    body = response.json()

    match = next(a for a in body if a["id"] == ctx["application_id"])
    assert match["job"]["id"] == ctx["job_id"]
    assert "company_name" in match["job"]
    assert "score" in match["job"]


def test_list_applications_filters_by_status():
    ctx_discovered = _setup_application(status=ApplicationStatus.discovered)
    ctx_queued = _setup_application(status=ApplicationStatus.queued)

    response = client.get("/applications", params={"status": "queued"})
    ids = [a["id"] for a in response.json()]

    assert ctx_queued["application_id"] in ids
    assert ctx_discovered["application_id"] not in ids


def test_list_applications_filters_by_multiple_statuses():
    ctx_discovered = _setup_application(status=ApplicationStatus.discovered)
    ctx_queued = _setup_application(status=ApplicationStatus.queued)
    ctx_offer = _setup_application(status=ApplicationStatus.offer)

    response = client.get("/applications", params=[("status", "discovered"), ("status", "queued")])
    ids = [a["id"] for a in response.json()]

    assert ctx_discovered["application_id"] in ids
    assert ctx_queued["application_id"] in ids
    assert ctx_offer["application_id"] not in ids


def test_list_applications_filters_by_role_type():
    ctx_intern = _setup_application(role_type=RoleType.internship)
    ctx_ft = _setup_application(role_type=RoleType.full_time)

    response = client.get("/applications", params={"role_type": "full_time"})
    ids = [a["id"] for a in response.json()]

    assert ctx_ft["application_id"] in ids
    assert ctx_intern["application_id"] not in ids


def test_list_applications_filters_by_company_id():
    ctx = _setup_application()
    other = _setup_application()

    response = client.get("/applications", params={"company_id": ctx["company_id"]})
    ids = [a["id"] for a in response.json()]

    assert ctx["application_id"] in ids
    assert other["application_id"] not in ids


def test_list_applications_filters_by_has_cover_letter():
    with_cl = _setup_application(with_cover_letter=True)
    without_cl = _setup_application(with_cover_letter=False)

    response = client.get("/applications", params={"has_cover_letter": "true"})
    ids = [a["id"] for a in response.json()]

    assert with_cl["application_id"] in ids
    assert without_cl["application_id"] not in ids


def test_list_applications_pagination():
    for _ in range(3):
        _setup_application()

    response = client.get("/applications", params={"page": 1, "page_size": 1})
    assert len(response.json()) <= 1


def test_get_application_detail_not_found():
    response = client.get("/applications/999999")
    assert response.status_code == 404


def test_get_application_detail_includes_full_context():
    ctx = _setup_application(with_cover_letter=True, with_resume=True)

    response = client.get(f"/applications/{ctx['application_id']}")
    assert response.status_code == 200
    body = response.json()

    assert body["job"]["id"] == ctx["job_id"]
    assert body["resume_version"]["pdf_path"] == "/fake/resume.pdf"
    assert "latex_source" not in body["resume_version"]
    assert body["cover_letter"]["content"] == "Body."
    assert "status_history" in body


def test_patch_status_valid_transition():
    ctx = _setup_application(status=ApplicationStatus.discovered)

    response = client.patch(f"/applications/{ctx['application_id']}/status", json={"status": "queued"})
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert len(response.json()["status_history"]) == 1


def test_patch_status_invalid_transition_returns_409():
    ctx = _setup_application(status=ApplicationStatus.discovered)

    response = client.patch(f"/applications/{ctx['application_id']}/status", json={"status": "offer"})
    assert response.status_code == 409


def test_patch_status_with_force_bypasses_validation():
    ctx = _setup_application(status=ApplicationStatus.discovered)

    response = client.patch(
        f"/applications/{ctx['application_id']}/status", json={"status": "offer", "force": True}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "offer"
    assert response.json()["status_history"][-1]["forced"] is True


def test_patch_status_with_note():
    ctx = _setup_application(status=ApplicationStatus.discovered)

    response = client.patch(
        f"/applications/{ctx['application_id']}/status", json={"status": "queued", "note": "applying now"}
    )
    assert response.json()["status_history"][-1]["note"] == "applying now"


def test_patch_status_not_found():
    response = client.patch("/applications/999999/status", json={"status": "queued"})
    assert response.status_code == 404


def test_patch_notes_replaces_field():
    ctx = _setup_application()

    response = client.patch(f"/applications/{ctx['application_id']}/notes", json={"notes": "great fit"})
    assert response.status_code == 200
    assert response.json()["notes"] == "great fit"

    response2 = client.patch(f"/applications/{ctx['application_id']}/notes", json={"notes": "updated"})
    assert response2.json()["notes"] == "updated"


def test_queue_job_creates_application_and_transitions_to_queued():
    n = _next_n()
    db = SessionLocal()
    try:
        company = Company(name=f"QueueCo{n}")
        db.add(company)
        db.commit()
        job = Job(
            company_id=company.id,
            title="SWE Intern",
            url=f"https://example.com/queue-job-{n}",
            source=JobSource.manual,
            role_type=RoleType.internship,
            job_family=JobFamily.consulting,
            dedup_hash=f"queuehash{n}",
        )
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()

    response = client.post(f"/jobs/{job_id}/queue")
    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_queue_job_is_idempotent_when_already_past_discovered():
    ctx = _setup_application(status=ApplicationStatus.in_progress)

    response = client.post(f"/jobs/{ctx['job_id']}/queue")
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"  # unchanged, not an error


def test_queue_job_not_found():
    response = client.post("/jobs/999999/queue")
    assert response.status_code == 404


def test_delete_application_allowed_when_discovered():
    ctx = _setup_application(status=ApplicationStatus.discovered)

    response = client.delete(f"/applications/{ctx['application_id']}")
    assert response.status_code == 204

    assert client.get(f"/applications/{ctx['application_id']}").status_code == 404


def test_delete_application_allowed_when_withdrawn():
    ctx = _setup_application(status=ApplicationStatus.withdrawn)

    response = client.delete(f"/applications/{ctx['application_id']}")
    assert response.status_code == 204


def test_delete_application_blocked_when_in_progress():
    ctx = _setup_application(status=ApplicationStatus.in_progress)

    response = client.delete(f"/applications/{ctx['application_id']}")
    assert response.status_code == 409


def test_delete_application_not_found():
    response = client.delete("/applications/999999")
    assert response.status_code == 404
