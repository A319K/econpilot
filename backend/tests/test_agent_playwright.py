"""Single Playwright integration test against a LOCAL static HTML fixture.

Marked `agent`; skipped automatically when Playwright isn't installed (see
conftest). Exercises the real snapshot/fill/upload/select path end-to-end: the
deterministic mapper fills the known fields, a mocked LLM answers one planted
ambiguous field, review detection fires, and the Submit button is provably
never clicked (asserted via a JS flag on the fixture)."""

import re
from pathlib import Path

import pytest

from app.agent.adapters.base import Adapter
from app.agent.loop import Caps, STATUS_READY, run_agent
from app.materials.cover_letter import build_profile_summary
from app.profile import get_profile

pytestmark = pytest.mark.agent

FIXTURE = Path(__file__).parent / "fixtures" / "apply_form.html"
CAPS = Caps(max_actions_per_step=40, max_page_steps=15, max_llm_calls=25, wall_clock_seconds=120)


async def _mock_llm(user: str) -> dict:
    # Find the ref of the planted ambiguous field from the prompt and fill it.
    match = re.search(r"ref=(\w+) label='What excites", user)
    assert match, f"expected the ambiguous field in the prompt:\n{user}"
    return {"action": "fill", "ref": match.group(1), "value": "The mission and the team."}


async def test_fills_fixture_reaches_review_never_submits(tmp_path):
    from app.agent.browser import PlaywrightBrowser

    # A real (tiny) file to upload into the file input.
    resume_pdf = tmp_path / "resume.pdf"
    resume_pdf.write_bytes(b"%PDF-1.4 fake\n")

    user_data_dir = tmp_path / "ctx"
    browser = await PlaywrightBrowser.launch(str(user_data_dir), headless=True)
    try:
        profile = get_profile()
        result = await run_agent(
            browser,
            adapter=Adapter(),
            profile=profile,
            profile_summary=build_profile_summary(profile),
            job_title="SWE Intern",
            company="Acme",
            resume_path=str(resume_pdf),
            cover_letter_path=None,
            apply_url=FIXTURE.as_uri(),
            llm_call=_mock_llm,
            caps=CAPS,
            screenshots_dir=str(tmp_path / "shots"),
            on_action=lambda e: None,
        )

        assert result.status == STATUS_READY

        # The submit button was provably never clicked.
        submitted = await browser.page.evaluate("window.__submitted")
        assert submitted is False

        # Deterministic fields were filled from the profile.
        assert await browser.page.input_value("#first_name") == "Jordan"
        assert await browser.page.input_value("#email") == str(profile.personal.email)
        # The mocked LLM answered the ambiguous field.
        assert await browser.page.input_value("#excites") == "The mission and the team."
        # The resume file was attached.
        file_count = await browser.page.evaluate("document.getElementById('resume').files.length")
        assert file_count == 1
        # EEO select resolved to the decline option.
        assert await browser.page.input_value("#gender") == "decline"
    finally:
        await browser.close()
