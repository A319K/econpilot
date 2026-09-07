"""Agent loop tests with a fake browser + scripted LLM - no real browser, no
real LLM. Covers the happy path to review, the submit-blocklist guard, and the
pause paths."""

import pytest

from app.agent import safety
from app.agent.adapters.base import Adapter
from app.agent.browser import BlocklistedClickError
from app.agent.loop import (
    Caps,
    STATUS_PAUSED,
    STATUS_READY,
    PAUSE_LOGIN,
    PAUSE_UNMAPPED,
    run_agent,
)
from app.profile import get_profile
from app.materials.cover_letter import build_profile_summary

CAPS = Caps(max_actions_per_step=40, max_page_steps=15, max_llm_calls=25, wall_clock_seconds=600)


class FakeBrowser:
    """In-memory AgentBrowser: mutates its snapshot on fills and enforces the
    submit blocklist on click exactly like PlaywrightBrowser."""

    def __init__(self, snapshot: list[dict]) -> None:
        self._elements = [dict(e) for e in snapshot]
        self.clicks: list[str] = []
        self.submitted = False
        self.screenshots: list[str] = []

    async def goto(self, url: str) -> None:
        pass

    async def snapshot(self) -> list[dict]:
        return [dict(e) for e in self._elements]

    def _find(self, ref: str) -> dict:
        return next(e for e in self._elements if e["ref"] == ref)

    async def fill(self, ref: str, value: str) -> None:
        self._find(ref)["value"] = value

    async def select(self, ref: str, option: str) -> None:
        self._find(ref)["value"] = option

    async def check(self, ref: str, value: bool = True) -> None:
        self._find(ref)["value"] = "true" if value else ""

    async def upload(self, ref: str, path: str) -> None:
        self._find(ref)["value"] = path

    async def click(self, ref: str, *, allow_apply_entry: bool = False) -> None:
        el = self._find(ref)
        text = el.get("label") or el.get("value") or ""
        if safety.is_blocklisted_click(text, allow_apply_entry=allow_apply_entry):
            raise BlocklistedClickError(f"refused {ref}")
        if safety.normalize(el.get("type")) == "submit":
            self.submitted = True  # would only happen if the guard failed
        self.clicks.append(ref)

    async def screenshot(self, path: str) -> None:
        self.screenshots.append(path)


class ScriptedLLM:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def __call__(self, user: str) -> dict:
        self.calls += 1
        if not self._responses:
            return {"action": "pause", "reason": "error"}
        return self._responses.pop(0)


def _form_snapshot() -> list[dict]:
    return [
        {"ref": "e1", "role": "textbox", "type": "text", "label": "First Name", "name": "first_name", "required": True, "value": ""},
        {"ref": "e2", "role": "textbox", "type": "email", "label": "Email", "name": "email", "required": True, "value": ""},
        {"ref": "e3", "role": "textbox", "type": "textarea", "label": "Why do you want to work here?", "name": "q", "required": True, "value": ""},
        {"ref": "e12", "role": "button", "type": "file", "label": "Resume", "name": "resume", "required": True, "value": ""},
        {"ref": "sub", "role": "button", "type": "submit", "label": "Submit Application", "value": ""},
    ]


async def _run(browser, llm, **overrides):
    profile = get_profile()
    kwargs = dict(
        adapter=Adapter(),
        profile=profile,
        profile_summary=build_profile_summary(profile),
        job_title="SWE Intern",
        company="Acme",
        resume_path="/tmp/resume.pdf",
        cover_letter_path=None,
        apply_url=None,  # already on the form -> skip goto/entry
        llm_call=llm,
        caps=CAPS,
        screenshots_dir="/tmp/agent_runs/test",
        on_action=lambda e: None,
    )
    kwargs.update(overrides)
    return await run_agent(browser, **kwargs)


async def test_reaches_review_and_never_submits():
    browser = FakeBrowser(_form_snapshot())
    llm = ScriptedLLM([{"action": "fill", "ref": "e3", "value": "Because it is a great team."}])

    result = await _run(browser, llm)

    assert result.status == STATUS_READY
    assert browser.submitted is False
    assert "sub" not in browser.clicks
    # The ambiguous field was filled by the LLM; deterministic fields by mapper.
    assert browser._find("e3")["value"] == "Because it is a great team."
    assert browser._find("e1")["value"] == "Jordan"
    assert browser._find("e12")["value"] == "/tmp/resume.pdf"
    assert llm.calls == 1
    assert any("review" in s for s in browser.screenshots)


async def test_waits_for_async_form_before_reasoning(monkeypatch):
    # Ashby/Workday-style: the form fields aren't present on the first snapshots
    # (the page shows "Fetching application form"), then appear. The loop must
    # poll until they render rather than snapshot an empty page and give up
    # (the real-world failure: "step_done but no next button").
    from app.agent import loop as loop_mod

    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(loop_mod.asyncio, "sleep", _no_sleep)

    class LazyFormBrowser(FakeBrowser):
        def __init__(self, snapshot, empty_polls):
            super().__init__(snapshot)
            self._empty_polls = empty_polls
            self.snapshot_calls = 0

        async def snapshot(self):
            self.snapshot_calls += 1
            if self.snapshot_calls <= self._empty_polls:
                return []  # form still loading -> no interactive fields yet
            return [dict(e) for e in self._elements]

    browser = LazyFormBrowser(_form_snapshot(), empty_polls=3)
    llm = ScriptedLLM([{"action": "fill", "ref": "e3", "value": "Because it is a great team."}])

    result = await _run(
        browser, llm, apply_url="https://jobs.ashbyhq.com/acme/x/application?embed=true"
    )

    # It waited out the empty snapshots and then filled the form to review.
    assert result.status == STATUS_READY
    assert browser.snapshot_calls > 3
    assert browser._find("e1")["value"] == "Jordan"
    assert browser._find("e12")["value"] == "/tmp/resume.pdf"


async def test_attempted_submit_click_is_rejected_and_run_pauses():
    browser = FakeBrowser(_form_snapshot())
    # The LLM keeps trying to click Submit; validation rejects it both times.
    llm = ScriptedLLM([
        {"action": "click", "ref": "sub"},
        {"action": "click", "ref": "sub"},
    ])

    result = await _run(browser, llm)

    assert result.status == STATUS_PAUSED
    assert browser.submitted is False
    assert "sub" not in browser.clicks
    assert llm.calls == 2  # original + one corrective retry


async def test_login_wall_pauses_immediately():
    snapshot = [
        {"ref": "e1", "role": "textbox", "type": "email", "label": "Email", "required": True, "value": ""},
        {"ref": "e2", "role": "textbox", "type": "password", "label": "Password", "required": True, "value": ""},
        {"ref": "e3", "role": "button", "type": "submit", "label": "Sign In", "value": ""},
    ]
    browser = FakeBrowser(snapshot)
    llm = ScriptedLLM([])
    result = await _run(browser, llm)
    assert result.status == STATUS_PAUSED
    assert result.pause_reason == PAUSE_LOGIN
    assert llm.calls == 0


async def test_required_sensitive_field_pauses_unmapped():
    snapshot = [
        {"ref": "e1", "role": "textbox", "type": "text", "label": "First Name", "name": "first_name", "required": True, "value": ""},
        {"ref": "e2", "role": "textbox", "type": "text", "label": "Desired Salary", "name": "salary", "required": True, "value": ""},
    ]
    browser = FakeBrowser(snapshot)
    llm = ScriptedLLM([])
    result = await _run(browser, llm)
    assert result.status == STATUS_PAUSED
    assert result.pause_reason == PAUSE_UNMAPPED
    assert browser.submitted is False


async def test_browser_guard_rejects_submit_click_directly():
    """Defense in depth: even if validation were bypassed, the browser click
    helper physically refuses a blocklisted click (same logic as
    PlaywrightBrowser.click)."""
    browser = FakeBrowser(_form_snapshot())
    with pytest.raises(BlocklistedClickError):
        await browser.click("sub")
    assert browser.submitted is False


async def test_llm_pause_is_honored():
    browser = FakeBrowser(_form_snapshot())
    llm = ScriptedLLM([{"action": "pause", "reason": "captcha"}])
    result = await _run(browser, llm)
    assert result.status == STATUS_PAUSED
    assert result.pause_reason == "captcha"
