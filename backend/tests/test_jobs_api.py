from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.discovery.base import RawJob
from app.main import app
from app.models.company import AtsType, Company
from app.models.job import JobFamily, JobSource, RoleType

client = TestClient(app)


def _make_company(**overrides) -> Company:
    db = SessionLocal()
    try:
        company = Company(name=overrides.pop("name", "Acme"), **overrides)
        db.add(company)
        db.commit()
        db.refresh(company)
        return company
    finally:
        db.close()


def test_create_manual_job():
    response = client.post(
        "/jobs/manual",
        json={
            "url": "https://example.com/careers/123",
            "title": "Backend Intern",
            "company_name": "Manual Co",
            "role_type": "internship",
            "notes": "found via referral",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["source"] == "manual"
    assert body["role_type"] == "internship"
    assert body["title"] == "Backend Intern"
    assert body["description"] == "found via referral"


def test_create_manual_job_defaults_company_and_title():
    response = client.post(
        "/jobs/manual",
        json={"url": "https://example.com/careers/999", "role_type": "full_time"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "https://example.com/careers/999"


def test_get_job_not_found():
    response = client.get("/jobs/999999")
    assert response.status_code == 404


def test_get_job_by_id():
    create_resp = client.post(
        "/jobs/manual",
        json={"url": "https://example.com/careers/1", "title": "SWE Intern", "role_type": "internship"},
    )
    job_id = create_resp.json()["id"]

    get_resp = client.get(f"/jobs/{job_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == job_id


def test_list_jobs_filters_by_role_type():
    client.post(
        "/jobs/manual",
        json={"url": "https://example.com/careers/2001", "role_type": "internship", "title": "Intern A"},
    )
    client.post(
        "/jobs/manual",
        json={"url": "https://example.com/careers/2002", "role_type": "full_time", "title": "FT A"},
    )

    response = client.get("/jobs", params={"role_type": "internship"})
    assert response.status_code == 200
    titles = [j["title"] for j in response.json()]
    assert "Intern A" in titles
    assert "FT A" not in titles


def test_list_jobs_sorted_by_score_desc():
    response = client.get("/jobs")
    assert response.status_code == 200
    scores = [j["score"] for j in response.json()]
    assert scores == sorted(scores, reverse=True)


def test_list_jobs_pagination():
    response = client.get("/jobs", params={"page": 1, "page_size": 1})
    assert response.status_code == 200
    assert len(response.json()) <= 1


def test_scan_endpoint_with_mocked_sources(monkeypatch):
    from app.discovery.sources.greenhouse import GreenhouseSource
    from app.discovery.sources.github_repo import GithubNewGradSource, GithubRepoSource

    company = _make_company(name="Scan Co", ats_type=AtsType.greenhouse, ats_board_id="scanco")

    async def fake_fetch(self, company):
        return [
            RawJob(
                title="Financial Analyst Intern",
                url="https://boards.greenhouse.io/scanco/jobs/1",
                location="Remote",
                source=JobSource.greenhouse,
                company_name="Scan Co",
            )
        ]

    async def empty_fetch(self, company):
        return []

    monkeypatch.setattr(GreenhouseSource, "fetch", fake_fetch)
    monkeypatch.setattr(GithubRepoSource, "fetch", empty_fetch)
    monkeypatch.setattr(GithubNewGradSource, "fetch", empty_fetch)

    response = client.post("/scan", json={"role_type": "all", "targets_only": False})
    assert response.status_code == 200
    body = response.json()
    assert body["companies_scanned"] >= 1
    assert body["new"] >= 1

    jobs_resp = client.get("/jobs", params={"company_id": company.id})
    assert jobs_resp.status_code == 200
    assert any(j["title"] == "Financial Analyst Intern" for j in jobs_resp.json())
    assert jobs_resp.json()[0]["score_breakdown"] is not None
