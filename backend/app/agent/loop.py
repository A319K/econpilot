"""The agent loop (§4): the dependency-injected orchestrator.

`run_agent` takes an AgentBrowser and an async `llm_call` (both easily faked),
so the whole loop - deterministic fills, LLM decisions, cap enforcement, review
detection, blocklist rejection - is exercised in tests with no real browser and
no real LLM. It performs no DB I/O: it reports each action through `on_action`
and returns a LoopResult; runs.py persists state and performs the state-machine
transition on ready_for_review.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.agent import mapping, safety
from app.agent.adapters.base import Adapter, button_text, buttons, is_button
from app.agent.browser import AgentBrowser, BlocklistedClickError
from app.agent.prompts import agent_user
from app.agent.types import (
    ACTION_CHECK,
    ACTION_CLICK,
    ACTION_FILL,
    ACTION_PAUSE,
    ACTION_REVIEW_REACHED,
    ACTION_SELECT,
    ACTION_STEP_DONE,
    ACTION_UPLOAD,
    Snapshot,
    find_element,
)
from app.agent.validation import validate_action
from app.profile import Profile

# Run outcomes.
STATUS_READY = "ready_for_review"
STATUS_PAUSED = "paused"
STATUS_FAILED = "failed"

# Pause reasons (mirror AgentRun.PauseReason values).
PAUSE_LOGIN = "login_required"
PAUSE_CAPTCHA = "captcha"
PAUSE_UNMAPPED = "unmapped_required_field"
PAUSE_CAP = "cap_exceeded"
PAUSE_ERROR = "error"

# LLM pause reasons we accept back and normalize.
_VALID_PAUSE_REASONS = {PAUSE_LOGIN, PAUSE_CAPTCHA, PAUSE_UNMAPPED, PAUSE_CAP, PAUSE_ERROR}

_LOGIN_KEYWORDS = ["sign in", "log in", "login", "create account", "register", "sign up"]

# Dynamic ATS (Ashby, Workday) fetch the application form via JS after the page
# loads, so an immediate snapshot sees a "Fetching application form" placeholder
# with zero fields. Poll the snapshot until interactive fields appear, up to
# this budget, before the agent reasons about the page. Server-rendered forms
# (Greenhouse, Lever) return fields on the first poll, adding no latency there.
FORM_READY_POLLS = 15
FORM_READY_DELAY_S = 1.0


async def _wait_for_form(browser: AgentBrowser) -> int:
    """Block until the page exposes interactive form fields (or the poll budget
    is exhausted), returning the field count seen. Returns as soon as any field
    is present, so it's a no-op on already-rendered forms."""
    fields = 0
    for _ in range(FORM_READY_POLLS):
        snapshot = await browser.snapshot()
        fields = sum(1 for el in snapshot if mapping._is_field(el))
        if fields:
            return fields
        await asyncio.sleep(FORM_READY_DELAY_S)
    return fields
_CAPTCHA_KEYWORDS = ["captcha", "recaptcha", "hcaptcha", "not a robot", "verify you are human"]

LlmCall = Callable[[str], Awaitable[dict]]
OnAction = Callable[[dict], None]
# Answer-bank hooks (DB-backed in runs.py, None/stubbed in tests). lookup
# returns an approved cached answer for a question label, or None; record saves
# an LLM answer as a suggestion.
AnswerLookup = Callable[[str], str | None]
AnswerRecord = Callable[[str, str], None]


@dataclass
class Caps:
    max_actions_per_step: int
    max_page_steps: int
    max_llm_calls: int
    wall_clock_seconds: int


@dataclass
class LoopResult:
    status: str
    pause_reason: str | None = None
    detail: str | None = None
    llm_calls: int = 0


def looks_like_login(snapshot: Snapshot) -> bool:
    """A login / account-creation / signup wall (§0 -> pause immediately)."""
    for el in snapshot:
        if safety.normalize(el.get("type")) == "password":
            return True
    for el in snapshot:
        if is_button(el) and any(k in safety.normalize(button_text(el)) for k in _LOGIN_KEYWORDS):
            return True
    return False


def looks_like_captcha(snapshot: Snapshot) -> bool:
    for el in snapshot:
        blob = safety.normalize(" ".join([el.get("label", ""), el.get("name", ""), el.get("type", "")]))
        if any(k in blob for k in _CAPTCHA_KEYWORDS):
            return True
    return False


def _visible_buttons(snapshot: Snapshot) -> list[dict]:
    """Non-submit buttons the LLM may reference for step_done."""
    return [el for el in buttons(snapshot) if not safety.is_blocklisted_click(button_text(el))]


async def _execute(browser: AgentBrowser, action: dict) -> str:
    """Run a validated field/click action against the browser. Returns a short
    result string. Raises BlocklistedClickError (never swallowed here)."""
    name = action["action"]
    ref = action.get("ref")
    value = action.get("value")
    if name == ACTION_FILL:
        await browser.fill(ref, str(value))
    elif name == ACTION_SELECT:
        await browser.select(ref, str(value))
    elif name == ACTION_CHECK:
        await browser.check(ref, bool(value) if value is not None else True)
    elif name == ACTION_UPLOAD:
        await browser.upload(ref, str(value))
    elif name == ACTION_CLICK:
        await browser.click(ref)
    return "ok"


async def run_agent(
    browser: AgentBrowser,
    *,
    adapter: Adapter,
    profile: Profile,
    profile_summary: str,
    job_title: str,
    company: str,
    resume_path: str | None,
    cover_letter_path: str | None,
    apply_url: str | None,
    llm_call: LlmCall,
    caps: Caps,
    screenshots_dir: str,
    on_action: OnAction,
    answer_lookup: AnswerLookup | None = None,
    answer_record: AnswerRecord | None = None,
    resume: bool = False,
) -> LoopResult:
    start = time.monotonic()
    llm_calls = 0
    standard_answers = profile.standard_answers.model_dump()
    # Refs whose deterministic action failed (rejected/blocked/errored) - never
    # retried, so a single un-actionable field can't loop or crash the run.
    failed_refs: set[str] = set()
    # Signatures (ref, action, value) already applied this run. Guarantees the
    # deterministic pass converges even when a field is React-controlled and
    # doesn't report its filled value back into the next snapshot.
    applied: set[tuple[str, str, str]] = set()

    def log(entry: dict) -> dict:
        entry = {**entry, "ts": time.time()}
        on_action(entry)
        return entry

    def over_time() -> bool:
        return (time.monotonic() - start) >= caps.wall_clock_seconds

    def cap_pause(detail: str) -> LoopResult:
        log({"event": "pause", "reason": PAUSE_CAP, "detail": detail})
        return LoopResult(STATUS_PAUSED, PAUSE_CAP, detail, llm_calls)

    # --- fresh start: navigate + enter the form ---------------------------
    if not resume and apply_url:
        await browser.goto(apply_url)
        log({"event": "goto", "url": apply_url})
        try:
            entered = await adapter.get_apply_entry(browser)
            log({"event": "apply_entry", "clicked": entered})
        except BlocklistedClickError as exc:
            log({"event": "pause", "reason": PAUSE_ERROR, "detail": str(exc)})
            return LoopResult(STATUS_PAUSED, PAUSE_ERROR, str(exc), llm_calls)

        # Wait out any JS-fetched form (Ashby/Workday) so we don't snapshot a
        # still-loading page and wrongly conclude there's nothing to fill.
        ready_fields = await _wait_for_form(browser)
        log({"event": "form_ready", "fields": ready_fields})

    # --- page-step loop ---------------------------------------------------
    for step in range(1, caps.max_page_steps + 1):
        if over_time():
            return cap_pause("wall clock exceeded")

        snapshot = await browser.snapshot()
        await browser.screenshot(f"{screenshots_dir}/step_{step}.png")
        log({"event": "step", "step": step, "fields": len(snapshot)})

        if looks_like_login(snapshot):
            log({"event": "pause", "reason": PAUSE_LOGIN, "detail": "login/signup wall detected"})
            return LoopResult(STATUS_PAUSED, PAUSE_LOGIN, "login/signup wall", llm_calls)
        if looks_like_captcha(snapshot):
            log({"event": "pause", "reason": PAUSE_CAPTCHA, "detail": "captcha detected"})
            return LoopResult(STATUS_PAUSED, PAUSE_CAPTCHA, "captcha", llm_calls)

        actions_this_step = 0

        # Inner loop: deterministic fills, then LLM for the remainder / control.
        while True:
            if over_time():
                return cap_pause("wall clock exceeded")
            if actions_this_step >= caps.max_actions_per_step:
                return cap_pause(f"max actions per step ({caps.max_actions_per_step})")

            result = mapping.map_fields(
                snapshot, profile, resume_path=resume_path, cover_letter_path=cover_letter_path
            )

            if result.must_pause:
                detail = result.must_pause[0].get("reason", "field cannot be answered")
                log({"event": "pause", "reason": PAUSE_UNMAPPED, "detail": detail})
                return LoopResult(STATUS_PAUSED, PAUSE_UNMAPPED, detail, llm_calls)

            # Execute any deterministically-resolved actions first, skipping refs
            # that already failed and (ref, action, value) signatures already
            # applied - so the pass always converges.
            def _sig(a: dict) -> tuple[str, str, str]:
                return (str(a.get("ref")), str(a.get("action")), str(a.get("value")))

            pending = [
                a
                for a in result.actions
                if a.get("ref") not in failed_refs and _sig(a) not in applied
            ]
            if pending:
                for action in pending:
                    ref = action.get("ref")
                    verdict = validate_action(action, snapshot)
                    if not verdict.ok:
                        # A deterministic action that fails validation (e.g.
                        # blocklisted) is a bug/safety-net; skip and log.
                        failed_refs.add(ref)
                        log({**action, "result": "rejected", "note": verdict.error})
                        continue
                    try:
                        res = await _execute(browser, action)
                        applied.add(_sig(action))
                        log({**action, "result": res, "source": "mapper"})
                    except BlocklistedClickError as exc:
                        failed_refs.add(ref)
                        log({**action, "result": "blocked", "note": str(exc)})
                    except Exception as exc:  # a control that can't be actioned
                        failed_refs.add(ref)
                        log({**action, "result": "error", "note": str(exc)[:200]})
                    actions_this_step += 1
                    if actions_this_step >= caps.max_actions_per_step:
                        return cap_pause(f"max actions per step ({caps.max_actions_per_step})")
                snapshot = await browser.snapshot()
                continue  # re-evaluate after fills

            # Answer-bank pass: fill unresolved free-text fields from approved
            # cached answers before spending an LLM call.
            if answer_lookup is not None:
                bank_filled = False
                for field in result.unresolved:
                    ref = field.get("ref")
                    if ref in failed_refs or field.get("options"):
                        continue
                    label = field.get("label") or field.get("name") or ""
                    cached = answer_lookup(label)
                    if not cached:
                        continue
                    action = {"action": ACTION_FILL, "ref": ref, "value": cached}
                    if _sig(action) in applied:
                        continue
                    verdict = validate_action(action, snapshot)
                    if not verdict.ok:
                        failed_refs.add(ref)
                        log({**action, "result": "rejected", "note": verdict.error, "source": "answer_bank"})
                        continue
                    try:
                        await _execute(browser, action)
                        applied.add(_sig(action))
                        log({**action, "result": "ok", "source": "answer_bank"})
                        bank_filled = True
                    except Exception as exc:
                        failed_refs.add(ref)
                        log({**action, "result": "error", "note": str(exc)[:200], "source": "answer_bank"})
                    actions_this_step += 1
                    if actions_this_step >= caps.max_actions_per_step:
                        return cap_pause(f"max actions per step ({caps.max_actions_per_step})")
                if bank_filled:
                    snapshot = await browser.snapshot()
                    continue

            # Nothing left to fill deterministically. Decide control flow.
            review_candidate = adapter.is_review_step(snapshot)
            unresolved = result.unresolved
            required_unresolved = [f for f in unresolved if f.get("required")]
            next_ref = adapter.next_button_ref(snapshot)

            # Confirmed review: no required field left and adapter agrees.
            if not required_unresolved and review_candidate:
                await browser.screenshot(f"{screenshots_dir}/step_{step}_review.png")
                log({"event": "review_reached", "step": step})
                return LoopResult(STATUS_READY, None, "agent reached review step", llm_calls)

            # All filled, not review, but there's a way forward: advance.
            if not unresolved and next_ref and not review_candidate:
                try:
                    await browser.click(next_ref)
                    log({"action": ACTION_CLICK, "ref": next_ref, "result": "ok", "source": "advance"})
                except BlocklistedClickError as exc:
                    log({"action": ACTION_CLICK, "ref": next_ref, "result": "blocked", "note": str(exc)})
                    return LoopResult(STATUS_PAUSED, PAUSE_ERROR, str(exc), llm_calls)
                break  # -> next page-step

            # Ambiguous: consult the LLM for one action.
            if llm_calls >= caps.max_llm_calls:
                return cap_pause(f"max LLM calls ({caps.max_llm_calls})")

            user = agent_user(
                job_title=job_title,
                company=company,
                ats_hints=adapter.step_hints(),
                profile_summary=profile_summary,
                standard_answers=standard_answers,
                unresolved_fields=unresolved,
                buttons=_visible_buttons(snapshot),
                review_candidate=review_candidate,
            )
            action, llm_calls, err = await _ask_llm(llm_call, user, snapshot, llm_calls)
            if err is not None:
                log({"event": "pause", "reason": PAUSE_ERROR, "detail": err})
                return LoopResult(STATUS_PAUSED, PAUSE_ERROR, err, llm_calls)

            outcome = await _handle_llm_action(
                action, browser, adapter, snapshot, screenshots_dir, step, log, llm_calls, answer_record
            )
            if isinstance(outcome, LoopResult):
                return outcome
            if outcome == "step_done":
                break  # -> next page-step
            # outcome == "continue": an action was executed; re-snapshot.
            actions_this_step += 1
            snapshot = await browser.snapshot()

    return cap_pause(f"max page steps ({caps.max_page_steps})")


async def _ask_llm(
    llm_call: LlmCall, user: str, snapshot: Snapshot, llm_calls: int
) -> tuple[dict | None, int, str | None]:
    """Call the LLM for one action, validate it, and give one corrective retry.
    Returns (action, new_llm_calls, error). error set -> caller pauses."""
    try:
        action = await llm_call(user)
    except Exception as exc:  # LLMError etc.
        return None, llm_calls + 1, f"LLM call failed: {exc}"
    llm_calls += 1

    verdict = validate_action(action, snapshot)
    if verdict.ok:
        return action, llm_calls, None

    corrective = (
        f"{user}\n\nYour previous action was rejected: {verdict.error}. "
        "Return a corrected single action."
    )
    try:
        action = await llm_call(corrective)
    except Exception as exc:
        return None, llm_calls + 1, f"LLM call failed: {exc}"
    llm_calls += 1

    verdict = validate_action(action, snapshot)
    if verdict.ok:
        return action, llm_calls, None
    return None, llm_calls, f"invalid action after retry: {verdict.error}"


async def _handle_llm_action(
    action: dict,
    browser: AgentBrowser,
    adapter: Adapter,
    snapshot: Snapshot,
    screenshots_dir: str,
    step: int,
    log: Callable[[dict], dict],
    llm_calls: int,
    answer_record: AnswerRecord | None = None,
) -> Any:
    """Dispatch a validated LLM action. Returns a LoopResult (terminal),
    the string "step_done", or "continue"."""
    name = action["action"]

    if name == ACTION_PAUSE:
        reason = action.get("reason")
        reason = reason if reason in _VALID_PAUSE_REASONS else PAUSE_ERROR
        log({"event": "pause", "reason": reason, "detail": action.get("reason")})
        return LoopResult(STATUS_PAUSED, reason, "LLM requested pause", llm_calls)

    if name == ACTION_REVIEW_REACHED:
        if adapter.is_review_step(snapshot):
            await browser.screenshot(f"{screenshots_dir}/step_{step}_review.png")
            log({"event": "review_reached", "step": step, "source": "llm"})
            return LoopResult(STATUS_READY, None, "agent reached review step", llm_calls)
        # LLM claims review but the adapter disagrees: don't trust it.
        log({"event": "review_rejected", "detail": "adapter is_review_step=False"})
        return LoopResult(
            STATUS_PAUSED, PAUSE_ERROR, "LLM claimed review but adapter disagreed", llm_calls
        )

    if name == ACTION_STEP_DONE:
        next_ref = adapter.next_button_ref(snapshot)
        if next_ref is None:
            log({"event": "pause", "reason": PAUSE_ERROR, "detail": "step_done but no next button"})
            return LoopResult(STATUS_PAUSED, PAUSE_ERROR, "no next button to advance", llm_calls)
        try:
            await browser.click(next_ref)
            log({"action": ACTION_CLICK, "ref": next_ref, "result": "ok", "source": "step_done"})
        except BlocklistedClickError as exc:
            log({"action": ACTION_CLICK, "ref": next_ref, "result": "blocked", "note": str(exc)})
            return LoopResult(STATUS_PAUSED, PAUSE_ERROR, str(exc), llm_calls)
        return "step_done"

    # Field/click action.
    try:
        res = await _execute(browser, action)
        log({**action, "result": res, "source": "llm"})
        # Remember a free-text answer the LLM produced, as a suggestion for
        # the human to approve (review-gated reuse next time).
        if answer_record is not None and action.get("action") == ACTION_FILL:
            element = find_element(snapshot, action.get("ref"))
            if element is not None and not element.get("options"):
                label = element.get("label") or element.get("name")
                if label:
                    answer_record(label, str(action.get("value")))
    except BlocklistedClickError as exc:
        # The submit guard fired on an LLM-chosen click: log + pause the run.
        log({**action, "result": "blocked", "note": str(exc)})
        return LoopResult(STATUS_PAUSED, PAUSE_ERROR, f"blocklisted click: {exc}", llm_calls)
    except Exception as exc:
        # The chosen action couldn't be applied (e.g. wrong control type):
        # log and pause rather than crash the run.
        log({**action, "result": "error", "note": str(exc)[:200]})
        return LoopResult(STATUS_PAUSED, PAUSE_ERROR, f"action failed: {exc}", llm_calls)
    return "continue"
