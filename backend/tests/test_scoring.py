from datetime import datetime, timedelta, timezone

from app.discovery.scoring import score
from app.models.company import Company
from app.models.job import Job, JobFamily, JobSource, RoleType
from app.profile import (
    Education,
    Personal,
    Profile,
    Project,
    Skills,
    StandardAnswers,
    WorkExperience,
)


def _profile(**skills_overrides) -> Profile:
    skills = Skills(languages=["Python", "R"], frameworks=[], tools=["Excel", "Stata"])
    for key, value in skills_overrides.items():
        setattr(skills, key, value)

    return Profile(
        personal=Personal(name="Test", email="test@example.com", phone="555", city="Boston", state="MA"),
        education=[Education(school="U", degree="BS", major="Economics", start="2023", end="2027")],
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
        title="Economic Consulting Analyst Intern",
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
    job = _job(title="Data Analyst", description="Python, R, and Excel experience preferred")
    profile = _profile()
    company = _company()

    total, breakdown = score(job, profile, company, now=datetime.now(timezone.utc))

    assert breakdown["keyword_overlap"] == 15.0
    assert set(breakdown["matched_keywords"]) == {"Python", "R", "Excel"}


def test_keyword_overlap_caps_at_25():
    many_skills = [f"skill{i}" for i in range(20)]
    profile = _profile(languages=many_skills)
    job = _job(title=" ".join(many_skills))
    company = _company()

    _, breakdown = score(job, profile, company, now=datetime.now(timezone.utc))
    assert breakdown["keyword_overlap"] == 25.0


def test_coursework_fit_rewards_shared_econ_coursework():
    profile = _profile(tools=["Econometrics", "Statistics", "Stata"])
    job = _job(description="Coursework in econometrics and statistics is required")

    _, breakdown = score(job, profile, _company(), now=datetime.now(timezone.utc))

    assert breakdown["coursework_fit"] == 10.0
    assert set(breakdown["matched_coursework"]) == {"econometrics", "statistics"}


def test_coursework_fit_does_not_reward_unheld_requirements():
    job = _job(description="Coursework in econometrics and linear algebra is required")

    _, breakdown = score(job, _profile(), _company(), now=datetime.now(timezone.utc))

    assert breakdown["coursework_fit"] == 0.0


def test_relevant_experience_uses_qualified_family_signals():
    profile = _profile()
    profile.work_experience = [
        WorkExperience(
            company="University Lab",
            title="Research Assistant",
            start="2025-01",
            end="2025-05",
            bullets=["Completed economic research and causal inference analysis"],
        )
    ]
    job = _job(job_family=JobFamily.policy_research)

    _, breakdown = score(job, profile, _company(), now=datetime.now(timezone.utc))

    assert breakdown["relevant_experience"] == 10.0
    assert set(breakdown["matched_experience_signals"]) == {
        "research assistant",
        "economic research",
    }


def test_generic_analyst_experience_is_not_a_domain_signal():
    profile = _profile()
    profile.projects = [
        Project(name="Retail Club", description="Analyst associate case", bullets=[])
    ]
    job = _job(job_family=JobFamily.consulting)

    _, breakdown = score(job, profile, _company(), now=datetime.now(timezone.utc))

    assert breakdown["relevant_experience"] == 0.0


def test_finance_internship_and_investment_club_count_as_relevant_experience():
    profile = _profile()
    profile.work_experience = [
        WorkExperience(
            company="Regional Bank",
            title="Finance Intern",
            start="2025-06",
            end="2025-08",
            bullets=["Presented an equity pitch for the investment club"],
        )
    ]
    job = _job(job_family=JobFamily.finance)

    _, breakdown = score(job, profile, _company(), now=datetime.now(timezone.utc))

    assert breakdown["relevant_experience"] == 10.0
    assert set(breakdown["matched_experience_signals"]) == {
        "finance intern",
        "investment club",
    }


def test_recency_within_24_hours():
    now = datetime.now(timezone.utc)
    job = _job(posted_at=now - timedelta(hours=5))
    _, breakdown = score(job, _profile(), _company(), now=now)
    assert breakdown["recency"] == 25.0


def test_recency_within_72_hours():
    now = datetime.now(timezone.utc)
    job = _job(posted_at=now - timedelta(hours=48))
    _, breakdown = score(job, _profile(), _company(), now=now)
    assert breakdown["recency"] == 18.0


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
    assert breakdown["target_company"] == 15.0

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
    assert breakdown["family_match"] == 15.0

    job_other = _job(job_family=JobFamily.other, posted_at=now)
    _, breakdown_other = score(job_other, _profile(), _company(), now=now)
    assert breakdown_other["family_match"] == 0.0


def test_total_score_sums_components():
    now = datetime.now(timezone.utc)
    job = _job(
        title="Economic Consulting Analyst",
        description="",
        posted_at=now - timedelta(hours=5),
        job_family=JobFamily.consulting,
    )
    profile = _profile()
    company = _company(is_target=True)

    total, breakdown = score(job, profile, company, now=now)

    expected = (
        breakdown["keyword_overlap"]
        + breakdown["coursework_fit"]
        + breakdown["relevant_experience"]
        + breakdown["recency"]
        + breakdown["target_company"]
        + breakdown["family_match"]
    )
    assert total == expected
    assert total <= 100.0
