from datetime import datetime, timedelta, timezone

from app.discovery.scoring import score
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.profile import (
    Education,
    Personal,
    Profile,
    Skills,
    StandardAnswers,
    WorkExperience,
)


def _profile(**skills_overrides) -> Profile:
    skills = Skills(languages=["Python", "TypeScript"], frameworks=["FastAPI"], tools=["Docker"])
    for key, value in skills_overrides.items():
        setattr(skills, key, value)

    return Profile(
        personal=Personal(name="Test", email="test@example.com", phone="555", city="Boston", state="MA"),
        education=[Education(school="U", degree="BS", major="CS", start="2023", end="2027")],
        work_experience=[],
        projects=[],
        skills=skills,
        standard_answers=StandardAnswers(
            work_authorization="citizen",
            requires_sponsorship=False,
            willing_to_relocate=True,
            graduation_date="2027-05",
        ),
    )


def _job(**overrides) -> Job:
    defaults = dict(
        id=1,
        company_id=1,
        title="Software Engineer Intern",
        location="Remote",
        url="https://example.com/1",
        source=JobSource.greenhouse,
        role_type=RoleType.internship,
        job_family=JobFamily.consulting,
        description="",
        posted_at=None,
        dedup_hash="hash",
    )
    defaults.update(overrides)
    return Job(**defaults)


def _company(**overrides) -> Company:
    defaults = dict(id=1, name="Acme", is_target=False)
    defaults.update(overrides)
    return Company(**defaults)


def test_keyword_overlap_matches_profile_skills():
    job = _job(title="Python FastAPI Engineer", description="Docker experience a plus")
    profile = _profile()
    company = _company()

    total, breakdown = score(job, profile, company, now=datetime.now(timezone.utc))

    assert breakdown["keyword_overlap"] == 15.0  # python, fastapi, docker = 3 * 5
    assert set(breakdown["matched_keywords"]) == {"Python", "FastAPI", "Docker"}


def test_keyword_overlap_caps_at_40():
    many_skills = [f"skill{i}" for i in range(20)]
    profile = _profile(languages=many_skills)
    job = _job(title=" ".join(many_skills))
    company = _company()

    _, breakdown = score(job, profile, company, now=datetime.now(timezone.utc))
    assert breakdown["keyword_overlap"] == 40.0


def test_recency_within_24_hours():
    now = datetime.now(timezone.utc)
    job = _job(posted_at=now - timedelta(hours=5))
    _, breakdown = score(job, _profile(), _company(), now=now)
    assert breakdown["recency"] == 30.0


def test_recency_within_72_hours():
    now = datetime.now(timezone.utc)
    job = _job(posted_at=now - timedelta(hours=48))
    _, breakdown = score(job, _profile(), _company(), now=now)
    assert breakdown["recency"] == 20.0


def test_recency_within_7_days():
    now = datetime.now(timezone.utc)
    job = _job(posted_at=now - timedelta(days=5))
    _, breakdown = score(job, _profile(), _company(), now=now)
    assert breakdown["recency"] == 10.0


def test_recency_stale():
    now = datetime.now(timezone.utc)
    job = _job(posted_at=now - timedelta(days=30))
    _, breakdown = score(job, _profile(), _company(), now=now)
    assert breakdown["recency"] == 0.0


def test_recency_unknown_posted_at():
    now = datetime.now(timezone.utc)
    job = _job(posted_at=None)
    _, breakdown = score(job, _profile(), _company(), now=now)
    assert breakdown["recency"] == 5.0


def test_target_company_bonus():
    now = datetime.now(timezone.utc)
    job = _job(posted_at=now)
    _, breakdown = score(job, _profile(), _company(is_target=True), now=now)
    assert breakdown["target_company"] == 20.0

    _, breakdown_no = score(job, _profile(), _company(is_target=False), now=now)
    assert breakdown_no["target_company"] == 0.0


def test_family_match_bonus_for_preferred_family(monkeypatch):
    from app.discovery import scoring as scoring_module

    settings = scoring_module.get_settings()
    monkeypatch.setattr(settings, "preferred_job_families", ["consulting"])
    monkeypatch.setattr(scoring_module, "get_settings", lambda: settings)

    now = datetime.now(timezone.utc)
    job = _job(job_family=JobFamily.consulting, posted_at=now)
    _, breakdown = score(job, _profile(), _company(), now=now)
    assert breakdown["family_match"] == 10.0

    job_other = _job(job_family=JobFamily.other, posted_at=now)
    _, breakdown_other = score(job_other, _profile(), _company(), now=now)
    assert breakdown_other["family_match"] == 0.0


def test_total_score_sums_components():
    now = datetime.now(timezone.utc)
    job = _job(
        title="Python FastAPI Engineer",
        description="",
        posted_at=now - timedelta(hours=5),
        job_family=JobFamily.consulting,
    )
    profile = _profile()
    company = _company(is_target=True)

    total, breakdown = score(job, profile, company, now=now)

    expected = (
        breakdown["keyword_overlap"]
        + breakdown["recency"]
        + breakdown["target_company"]
        + breakdown["family_match"]
    )
    assert total == expected
    assert total <= 100.0
