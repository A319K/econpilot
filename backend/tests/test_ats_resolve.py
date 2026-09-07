"""Tests for discovery.ats_resolve: application URL -> (AtsType, board_id).

The board_id must equal the org slug the keyless list APIs expect, so these
assert against real URL shapes seen in SimplifyJobs listings."""

from app.discovery.ats_resolve import resolve_ats
from app.models.company import AtsType


def test_greenhouse_board_url():
    assert resolve_ats("https://boards.greenhouse.io/stripe/jobs/12345") == (
        AtsType.greenhouse,
        "stripe",
    )


def test_greenhouse_job_boards_host():
    assert resolve_ats("https://job-boards.greenhouse.io/airbnb/jobs/678") == (
        AtsType.greenhouse,
        "airbnb",
    )


def test_greenhouse_embed_uses_for_param():
    url = "https://boards.greenhouse.io/embed/job_app?for=databricks&token=99"
    assert resolve_ats(url) == (AtsType.greenhouse, "databricks")


def test_lever_url():
    assert resolve_ats("https://jobs.lever.co/plaid/abc-123/apply") == (
        AtsType.lever,
        "plaid",
    )


def test_lever_eu_host():
    assert resolve_ats("https://jobs.eu.lever.co/spotify/xyz") == (AtsType.lever, "spotify")


def test_ashby_url():
    assert resolve_ats("https://jobs.ashbyhq.com/ramp/uuid-here/application") == (
        AtsType.ashby,
        "ramp",
    )


def test_workday_encodes_host_and_site_as_board_id():
    url = "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/US/Intern_JR1"
    assert resolve_ats(url) == (
        AtsType.workday,
        "nvidia.wd5.myworkdayjobs.com|NVIDIAExternalCareerSite",
    )


def test_workday_skips_locale_prefix_before_site():
    url = "https://acme.wd1.myworkdayjobs.com/en-US/AcmeCareers/job/Boston/Intern_R123"
    assert resolve_ats(url) == (AtsType.workday, "acme.wd1.myworkdayjobs.com|AcmeCareers")


def test_workday_bare_host_without_site_has_no_board_id():
    assert resolve_ats("https://acme.wd1.myworkdayjobs.com/") == (AtsType.workday, None)


def test_unrecognized_host_is_unknown():
    assert resolve_ats("https://stripe.com/jobs/listing/intern/123") == (
        AtsType.unknown,
        None,
    )


def test_scheme_less_url_still_parses_host():
    assert resolve_ats("jobs.lever.co/acme/1") == (AtsType.lever, "acme")


def test_none_and_empty_are_unknown():
    assert resolve_ats(None) == (AtsType.unknown, None)
    assert resolve_ats("") == (AtsType.unknown, None)
