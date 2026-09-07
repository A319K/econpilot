from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType

client = TestClient(app)


def _make_job(jd_keywords=None) -> int:
    db = SessionLocal()
    try:
        company = Company(name="KeywordCo")
        db.add(company)
        db.commit()
        job = Job(
            company_id=company.id,
            title="SWE Intern",
            url=f"https://example.com/kw-job-{company.id}",
            source=JobSource.manual,
            role_type=RoleType.internship,
            job_family=JobFamily.swe,
            dedup_hash=f"kwhash{company.id}",
            jd_keywords=jd_keywords,
        )
        db.add(job)
        db.commit()
        return job.id
    finally:
        db.close()


def test_get_job_keywords_returns_cached_keywords():
    job_id = _make_job(jd_keywords={"skills": ["Python"], "responsibilities": [], "qualifications": [], "nice_to_have": []})

    response = client.get(f"/frontend-support/jobs/{job_id}/keywords")
    assert response.status_code == 200
    assert response.json()["jd_keywords"]["skills"] == ["Python"]


def test_get_job_keywords_null_when_not_yet_extracted():
    job_id = _make_job(jd_keywords=None)

    response = client.get(f"/frontend-support/jobs/{job_id}/keywords")
    assert response.status_code == 200
    assert response.json()["jd_keywords"] is None


def test_get_job_keywords_not_found():
    response = client.get("/frontend-support/jobs/999999/keywords")
    assert response.status_code == 404
