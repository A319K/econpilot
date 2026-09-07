"""Run orchestration (§5): create/execute/resume/abandon an AgentRun, own the
background task's DB session and the shared browser lifecycle, and perform the
state-machine transition to ready_to_submit when the agent reaches review.

The HTTP handlers stay thin: they validate, create the row, and schedule
execute_run as a background asyncio task, returning the run id immediately.
"""

import asyncio
import re
import shutil
from pathlib import Path

from app.agent import answer_bank, loop
from app.agent.adapters.detect import get_adapter
from app.agent.loop import Caps, LoopResult
from app.agent.prompts import AGENT_SCHEMA_HINT, AGENT_SYSTEM
from app.agent.session import get_session
from app.config import get_settings
from app.db import SessionLocal
from app.llm.client import complete_json
from app.materials.cover_letter import build_profile_summary
from app.models.agent_run import AgentRun, AgentRunStatus, PauseReason
from app.models.application import Application, ApplicationStatus
from app.models.mixins import utcnow
from app.profile import get_profile
from app.tracking.state_machine import transition

# backend/app/agent/runs.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]


class AgentRunError(Exception):
    """Raised for invalid run operations (bad state, missing materials)."""


def _screenshots_dir(run_id: int) -> str:
    settings = get_settings()
    return str(REPO_ROOT / settings.output_dir / "agent_runs" / str(run_id))


def _company_slug(company: str) -> str:
    """Filename-safe form of a company name: lowercase, non-alphanumerics
    collapsed to single underscores (e.g. 'A&A Prep Inc.' -> 'a_a_prep_inc')."""
    slug = re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")
    return slug or "company"


def _stage_resume_for_company(resume_path: str | None, company: str) -> str | None:
    """Copy the resume PDF to a per-company filename ('<company>_resume.pdf') so
    the form upload presents it named after the employer, without touching the
    canonical source file. Falls back to the original path if the source is
    missing (the loop will pause on a required upload it can't satisfy)."""
    if not resume_path:
        return resume_path
    src = Path(resume_path)
    if not src.exists():
        return resume_path
    staging_dir = REPO_ROOT / get_settings().output_dir / "staged_resumes"
    staging_dir.mkdir(parents=True, exist_ok=True)
    dest = staging_dir / f"{_company_slug(company)}_resume{src.suffix or '.pdf'}"
    shutil.copy2(src, dest)
    return str(dest)


def _make_llm_call():
    async def call(user: str) -> dict:
        return await complete_json(AGENT_SYSTEM, user, AGENT_SCHEMA_HINT, max_tokens=1500)

    return call


def _caps() -> Caps:
    s = get_settings()
    return Caps(
        max_actions_per_step=s.agent_max_actions_per_step,
        max_page_steps=s.agent_max_page_steps,
        max_llm_calls=s.agent_max_llm_calls,
        wall_clock_seconds=s.agent_wall_clock_seconds,
    )


def create_run(db, application_id: int) -> AgentRun:
    """Create the AgentRun row (status running). Caller has already validated
    the application + global single-run guard."""
    run = AgentRun(application_id=application_id, status=AgentRunStatus.running, action_log=[])
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def schedule(run_id: int, *, resume: bool = False) -> None:
    """Launch the background execution task, keeping a reference on the session
    so it isn't garbage-collected."""
    session = get_session()
    session.task = asyncio.create_task(execute_run(run_id, resume=resume))


async def _get_browser(resume: bool):
    """Reuse the shared browser if present (always on resume); otherwise launch
    a fresh headed persistent context."""
    from app.agent.browser import PlaywrightBrowser  # lazy: needs playwright

    session = get_session()
    if session.browser is not None:
        return session.browser
    settings = get_settings()
    context_dir = str(REPO_ROOT / settings.agent_context_dir)
    browser = await PlaywrightBrowser.launch(context_dir, headless=False)
    session.browser = browser
    return browser


async def execute_run(run_id: int, *, resume: bool = False) -> None:
    """Background task: drive the loop for one run and persist its outcome."""
    db = SessionLocal()
    session = get_session()
    session.active_run_id = run_id
    try:
        run = db.get(AgentRun, run_id)
        if run is None:
            return
        application = db.get(Application, run.application_id)
        job = application.job
        company = job.company.name

        # Starting active work: queued -> in_progress (mirrors prepare.py).
        if application.status == ApplicationStatus.queued:
            transition(application, ApplicationStatus.in_progress, note="autofill started")
            db.commit()

        profile = get_profile()
        profile_summary = build_profile_summary(profile)
        adapter = get_adapter(job.url)

        resume_path = application.resume_version.pdf_path if application.resume_version else None
        # Upload the resume under a per-company name ("<company>_resume.pdf")
        # without altering the canonical source file.
        resume_path = _stage_resume_for_company(resume_path, company)
        cover_letter_path = (
            application.cover_letter.pdf_path if application.cover_letter else None
        )

        screenshots_dir = _screenshots_dir(run_id)
        run.screenshots_dir = screenshots_dir
        run.status = AgentRunStatus.running
        run.pause_reason = None
        db.commit()

        def on_action(entry: dict) -> None:
            run.action_log = [*(run.action_log or []), entry]
            db.commit()

        def answer_lookup(question: str) -> str | None:
            return answer_bank.lookup(db, question)

        def answer_record(question: str, answer: str) -> None:
            answer_bank.record_llm_answer(db, question, answer)

        browser = await _get_browser(resume)

        result: LoopResult = await loop.run_agent(
            browser,
            adapter=adapter,
            profile=profile,
            profile_summary=profile_summary,
            job_title=job.title,
            company=company,
            resume_path=resume_path,
            cover_letter_path=cover_letter_path,
            apply_url=job.url,
            llm_call=_make_llm_call(),
            caps=_caps(),
            screenshots_dir=screenshots_dir,
            on_action=on_action,
            answer_lookup=answer_lookup,
            answer_record=answer_record,
            resume=resume,
        )

        _finalize(db, run, application, result)
    except Exception as exc:  # never let a background task die silently
        _fail(db, run_id, str(exc))
    finally:
        session.active_run_id = None
        db.close()


def _finalize(db, run: AgentRun, application: Application, result: LoopResult) -> None:
    run.llm_calls = result.llm_calls
    if result.status == loop.STATUS_READY:
        run.status = AgentRunStatus.ready_for_review
        run.ended_at = utcnow()
        # Reuse the state machine; note per spec.
        if application.status == ApplicationStatus.in_progress:
            transition(
                application,
                ApplicationStatus.ready_to_submit,
                note="agent reached review step",
            )
    elif result.status == loop.STATUS_PAUSED:
        run.status = AgentRunStatus.paused
        run.pause_reason = PauseReason(result.pause_reason) if result.pause_reason else PauseReason.error
    else:
        run.status = AgentRunStatus.failed
        run.pause_reason = PauseReason.error
        run.ended_at = utcnow()
    db.commit()


def _fail(db, run_id: int, detail: str) -> None:
    run = db.get(AgentRun, run_id)
    if run is None:
        return
    run.action_log = [*(run.action_log or []), {"event": "error", "detail": detail}]
    run.status = AgentRunStatus.failed
    run.pause_reason = PauseReason.error
    run.ended_at = utcnow()
    db.commit()


def resume_run(db, run_id: int) -> AgentRun:
    """Validate a paused run and schedule its continuation (re-snapshot)."""
    run = db.get(AgentRun, run_id)
    if run is None:
        raise AgentRunError("run not found")
    if run.status != AgentRunStatus.paused:
        raise AgentRunError(f"can only resume a paused run (status is {run.status.value})")
    run.status = AgentRunStatus.running
    run.pause_reason = None
    db.commit()
    schedule(run_id, resume=True)
    db.refresh(run)
    return run


def abandon_run(db, run_id: int) -> AgentRun:
    """Mark a run abandoned. The browser is left open for the human (§5)."""
    run = db.get(AgentRun, run_id)
    if run is None:
        raise AgentRunError("run not found")
    if run.status not in {AgentRunStatus.running, AgentRunStatus.paused}:
        raise AgentRunError(f"can only abandon an active run (status is {run.status.value})")
    run.status = AgentRunStatus.abandoned
    run.ended_at = utcnow()
    run.action_log = [*(run.action_log or []), {"event": "abandoned"}]
    db.commit()
    session = get_session()
    if session.active_run_id == run_id:
        session.active_run_id = None
    db.refresh(run)
    return run
