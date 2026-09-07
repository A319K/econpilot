"""API tests for the autofill + agent-run endpoints, with the agent runner
mocked (no browser, no LLM, no background task actually launched)."""

from fastapi.testclient import TestClient

from app.agent import runs as agent_runs
from app.agent.session import get_session
from app.db import SessionLocal
from app.main import app
from app.models.agent_run import AgentRun, AgentRunStatus, PauseReason
from app.models.application import Application, ApplicationStatus
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.models.resume_version import ResumeVersion

client = TestClient(app)

_counter = {"n": 0}


def _next_n() -> int:
    _counter["n"] += 1
    return _counter["n"]


def _make_application(status=ApplicationStatus.in_progress, with_resume_pdf=True) -> int:
    n = _next_n()
    db = SessionLocal()
    try:
        company = Company(name=f"AgentCo{n}")
        db.add(company)
        db.commit()
        job = Job(
            company_id=company.id,
            title=f"SWE Intern {n}",
            url=f"https://boards.greenhouse.io/agentco{n}/jobs/{n}",
            source=JobSource.greenhouse,
            role_type=RoleType.internship,
            job_family=JobFamily.swe,
            dedup_hash=f"agenthash{n}",
            score=50.0,
        )
        db.add(job)
        db.commit()
        resume = ResumeVersion(
            name=f"Resume {n}",
            job_family=JobFamily.swe,
            latex_source="x",
            pdf_path=f"/tmp/resume_{n}.pdf" if with_resume_pdf else None,
        )
        db.add(resume)
        db.commit()
        application = Application(job_id=job.id, status=status, resume_version_id=resume.id)
        db.add(application)
        db.commit()
        return application.id
    finally:
        db.close()


def _clear_active_runs():
    """Reset the global single-run guard between tests."""
    db = SessionLocal()
    try:
        for run in db.query(AgentRun).filter(
            AgentRun.status.in_([AgentRunStatus.running, AgentRunStatus.paused])
        ):
            run.status = AgentRunStatus.abandoned
        db.commit()
    finally:
        db.close()
    get_session().active_run_id = None


def _patch_schedule(monkeypatch):
    """Stop the endpoint from actually launching a background browser task."""
    launched = []
    monkeypatch.setattr(agent_runs, "schedule", lambda run_id, resume=False: launched.append((run_id, resume)))
    return launched


def test_autofill_creates_run_and_schedules(monkeypatch):
    _clear_active_runs()
    launched = _patch_schedule(monkeypatch)
    app_id = _make_application()

    resp = client.post(f"/applications/{app_id}/autofill")
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    assert body["application_id"] == app_id
    assert launched == [(body["id"], False)]


def test_autofill_requires_valid_status(monkeypatch):
    _clear_active_runs()
    _patch_schedule(monkeypatch)
    app_id = _make_application(status=ApplicationStatus.submitted)
    resp = client.post(f"/applications/{app_id}/autofill")
    assert resp.status_code == 409
    assert "queued or in_progress" in resp.json()["detail"]


def test_autofill_requires_resume_pdf(monkeypatch):
    _clear_active_runs()
    _patch_schedule(monkeypatch)
    app_id = _make_application(with_resume_pdf=False)
    resp = client.post(f"/applications/{app_id}/autofill")
    assert resp.status_code == 409
    assert "resume" in resp.json()["detail"].lower()


def test_autofill_409_when_run_already_active(monkeypatch):
    _clear_active_runs()
    _patch_schedule(monkeypatch)
    app_id = _make_application()

    first = client.post(f"/applications/{app_id}/autofill")
    assert first.status_code == 202

    # A second application can't start while the first run is active.
    other = _make_application()
    resp = client.post(f"/applications/{other}/autofill")
    assert resp.status_code == 409
    assert "already active" in resp.json()["detail"]


def test_autofill_unknown_application():
    resp = client.post("/applications/999999/autofill")
    assert resp.status_code == 404


def test_get_agent_run():
    _clear_active_runs()
    app_id = _make_application()
    db = SessionLocal()
    try:
        run = AgentRun(
            application_id=app_id,
            status=AgentRunStatus.paused,
            pause_reason=PauseReason.login_required,
            action_log=[{"event": "step", "step": 1}],
        )
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    resp = client.get(f"/agent-runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "paused"
    assert body["pause_reason"] == "login_required"
    assert body["action_log"] == [{"event": "step", "step": 1}]


def test_get_agent_run_404():
    assert client.get("/agent-runs/999999").status_code == 404


def test_resume_run(monkeypatch):
    _clear_active_runs()
    launched = _patch_schedule(monkeypatch)
    app_id = _make_application()
    db = SessionLocal()
    try:
        run = AgentRun(
            application_id=app_id,
            status=AgentRunStatus.paused,
            pause_reason=PauseReason.login_required,
        )
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    resp = client.post(f"/agent-runs/{run_id}/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"
    assert launched == [(run_id, True)]


def test_resume_non_paused_run_409(monkeypatch):
    _clear_active_runs()
    _patch_schedule(monkeypatch)
    app_id = _make_application()
    db = SessionLocal()
    try:
        run = AgentRun(application_id=app_id, status=AgentRunStatus.running)
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    resp = client.post(f"/agent-runs/{run_id}/resume")
    assert resp.status_code == 409


def test_abandon_run():
    _clear_active_runs()
    app_id = _make_application()
    db = SessionLocal()
    try:
        run = AgentRun(application_id=app_id, status=AgentRunStatus.paused)
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    resp = client.post(f"/agent-runs/{run_id}/abandon")
    assert resp.status_code == 200
    assert resp.json()["status"] == "abandoned"
    # Now a new run may start again.
    _clear_active_runs()
