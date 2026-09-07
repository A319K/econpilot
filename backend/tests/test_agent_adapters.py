import pytest

from app.agent.adapters import detect_ats, get_adapter
from app.agent.adapters.base import Adapter


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://boards.greenhouse.io/acme/jobs/123", "greenhouse"),
        ("https://job-boards.greenhouse.io/acme/jobs/123", "greenhouse"),
        ("https://jobs.lever.co/acme/abc-123", "lever"),
        ("https://jobs.ashbyhq.com/acme/xyz", "ashby"),
        ("https://acme.wd1.myworkdayjobs.com/en-US/careers/job/123", "workday"),
        ("https://acme.workday.com/careers", "workday"),
        ("https://careers.acme.com/apply/123", "generic"),
        ("not-a-url", "generic"),
    ],
)
def test_detect_ats(url, expected):
    assert detect_ats(url) == expected


def test_get_adapter_returns_matching_adapter():
    assert get_adapter("https://boards.greenhouse.io/x").name == "greenhouse"
    assert get_adapter("https://careers.acme.com/x").name == "generic"


def test_step_hints_are_nonempty_strings():
    for url in [
        "https://boards.greenhouse.io/x",
        "https://jobs.lever.co/x",
        "https://jobs.ashbyhq.com/x",
        "https://x.myworkdayjobs.com/y",
        "https://careers.acme.com/x",
    ]:
        assert isinstance(get_adapter(url).step_hints(), str)
        assert get_adapter(url).step_hints()


def test_generic_is_review_step_requires_submit_and_no_empty_required():
    adapter = Adapter()
    filled_with_submit = [
        {"ref": "e1", "role": "textbox", "type": "text", "label": "Name", "required": True, "value": "Jordan"},
        {"ref": "e2", "role": "button", "type": "submit", "label": "Submit Application", "value": ""},
    ]
    assert adapter.is_review_step(filled_with_submit) is True

    # An empty required field means it's not the review step yet.
    empty_required = [
        {"ref": "e1", "role": "textbox", "type": "text", "label": "Name", "required": True, "value": ""},
        {"ref": "e2", "role": "button", "type": "submit", "label": "Submit Application", "value": ""},
    ]
    assert adapter.is_review_step(empty_required) is False

    # No submit button present -> not review.
    no_submit = [
        {"ref": "e1", "role": "textbox", "type": "text", "label": "Name", "required": True, "value": "Jordan"},
        {"ref": "e2", "role": "button", "type": "button", "label": "Next", "value": ""},
    ]
    assert adapter.is_review_step(no_submit) is False


def test_next_button_ref_ignores_submit():
    adapter = Adapter()
    snapshot = [
        {"ref": "e1", "role": "button", "type": "button", "label": "Continue", "value": ""},
        {"ref": "e2", "role": "button", "type": "submit", "label": "Submit Application", "value": ""},
    ]
    assert adapter.next_button_ref(snapshot) == "e1"

    only_submit = [
        {"ref": "e2", "role": "button", "type": "submit", "label": "Submit Application", "value": ""},
    ]
    assert adapter.next_button_ref(only_submit) is None
