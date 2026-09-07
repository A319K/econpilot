import pytest

from app.agent import safety


@pytest.mark.parametrize(
    "text",
    [
        "Submit",
        "submit application",
        "Submit Application",
        "SUBMIT  APPLICATION",
        "submit_application",
        "Submit!",
        "Send Application",
        "Complete Application",
        "Finish",
        "  finish  ",
    ],
)
def test_blocklisted_clicks_are_rejected(text):
    assert safety.is_blocklisted_click(text) is True
    assert safety.blocklisted_reason(text) is not None


@pytest.mark.parametrize(
    "text",
    ["Next", "Continue", "Save and Continue", "Add another", "Back", "Upload resume", ""],
)
def test_safe_clicks_are_allowed(text):
    assert safety.is_blocklisted_click(text) is False


def test_apply_now_blocked_for_llm_but_allowed_for_entry():
    assert safety.is_blocklisted_click("Apply Now") is True
    # The deterministic entry click may open the form with "Apply Now"...
    assert safety.is_blocklisted_click("Apply Now", allow_apply_entry=True) is False
    # ...but the unconditional submit terms stay blocked even for entry.
    assert safety.is_blocklisted_click("Submit Application", allow_apply_entry=True) is True


def test_apply_for_this_job_is_not_blocklisted():
    # The common entry button must not trip the "apply now" rule.
    assert safety.is_blocklisted_click("Apply for this job") is False


@pytest.mark.parametrize(
    "fragments",
    [
        ("Password",),
        ("SSN",),
        ("Social Security Number",),
        ("Salary Expectation",),
        ("Expected Salary",),
        ("Credit Card Number",),
        ("password", "text"),
    ],
)
def test_sensitive_fields_detected(fragments):
    assert safety.is_sensitive_field(*fragments) is True
    assert safety.sensitive_reason(*fragments) is not None


@pytest.mark.parametrize("fragments", [("First Name",), ("Email",), ("Phone",), ("",)])
def test_non_sensitive_fields(fragments):
    assert safety.is_sensitive_field(*fragments) is False


def test_normalize():
    assert safety.normalize("  Hello_World!! ") == "hello world"
    assert safety.normalize(None) == ""
