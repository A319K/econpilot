"""Answer bank: matching, review-gating, record/upsert, and the loop
integration (a cached approved answer fills the field with NO LLM call)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent import answer_bank
from app.agent.adapters.base import Adapter
from app.agent.loop import Caps, STATUS_READY, run_agent
from app.db import Base
from app.materials.cover_letter import build_profile_summary
from app.models.answer_bank import AnswerBankEntry, AnswerSource
from app.profile import get_profile
from tests.test_agent_loop import FakeBrowser, ScriptedLLM

CAPS = Caps(max_actions_per_step=40, max_page_steps=15, max_llm_calls=25, wall_clock_seconds=600)


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _add(db, question, answer, *, approved, source=AnswerSource.user):
    entry = AnswerBankEntry(
        question_norm=answer_bank.normalize_question(question),
        question_raw=question,
        answer=answer,
        source=source,
        approved=approved,
    )
    db.add(entry)
    db.commit()
    return entry


def test_exact_match_lookup_and_usage_counter():
    db = _session()
    _add(db, "Why do you want to work here?", "I admire the mission.", approved=True)
    assert answer_bank.lookup(db, "why do you WANT to work here??") == "I admire the mission."
    entry = db.query(AnswerBankEntry).one()
    assert entry.times_used == 1
    assert entry.last_used_at is not None


def test_unapproved_answers_are_not_reused():
    db = _session()
    _add(db, "Notice period?", "Two weeks.", approved=False, source=AnswerSource.llm)
    assert answer_bank.lookup(db, "Notice period?") is None


def test_fuzzy_match_reworded_question():
    db = _session()
    _add(db, "How did you hear about this position?", "Through a friend.", approved=True)
    # Slight rewording still matches above the fuzzy threshold.
    assert answer_bank.lookup(db, "How did you hear about this position") == "Through a friend."


def test_fuzzy_does_not_match_unrelated():
    db = _session()
    _add(db, "How did you hear about this position?", "Through a friend.", approved=True)
    assert answer_bank.lookup(db, "What is your greatest weakness?") is None


def test_record_llm_answer_is_pending_suggestion():
    db = _session()
    entry = answer_bank.record_llm_answer(db, "What excites you about this role?", "The team.")
    assert entry is not None
    assert entry.approved is False
    assert entry.source == AnswerSource.llm
    # And it is not reused until approved.
    assert answer_bank.lookup(db, "What excites you about this role?") is None


def test_record_does_not_overwrite_approved():
    db = _session()
    _add(db, "Q?", "approved answer", approved=True)
    answer_bank.record_llm_answer(db, "Q?", "llm answer")
    entry = db.query(AnswerBankEntry).one()
    assert entry.answer == "approved answer"  # untouched
    assert entry.approved is True


def test_record_refreshes_pending_suggestion():
    db = _session()
    answer_bank.record_llm_answer(db, "Q?", "first")
    answer_bank.record_llm_answer(db, "Q?", "second")
    entry = db.query(AnswerBankEntry).one()
    assert entry.answer == "second"
    assert db.query(AnswerBankEntry).count() == 1


# --- loop integration -----------------------------------------------------


def _form_snapshot() -> list[dict]:
    return [
        {"ref": "e1", "role": "textbox", "type": "text", "label": "First Name", "name": "first_name", "required": True, "value": ""},
        {"ref": "e2", "role": "textbox", "type": "email", "label": "Email", "name": "email", "required": True, "value": ""},
        {"ref": "e3", "role": "textbox", "type": "textarea", "label": "Why do you want to work here?", "name": "q", "required": True, "value": ""},
        {"ref": "e12", "role": "button", "type": "file", "label": "Resume", "name": "resume", "required": True, "value": ""},
        {"ref": "sub", "role": "button", "type": "submit", "label": "Submit Application", "value": ""},
    ]


async def test_cached_answer_fills_field_without_calling_llm():
    db = _session()
    _add(db, "Why do you want to work here?", "Because the mission resonates.", approved=True)

    browser = FakeBrowser(_form_snapshot())
    llm = ScriptedLLM([])  # empty: if the LLM is called at all, it would pause
    profile = get_profile()

    result = await run_agent(
        browser,
        adapter=Adapter(),
        profile=profile,
        profile_summary=build_profile_summary(profile),
        job_title="SWE Intern",
        company="Acme",
        resume_path="/tmp/resume.pdf",
        cover_letter_path=None,
        apply_url=None,
        llm_call=llm,
        caps=CAPS,
        screenshots_dir="/tmp/agent_runs/bank",
        on_action=lambda e: None,
        answer_lookup=lambda q: answer_bank.lookup(db, q),
        answer_record=lambda q, a: answer_bank.record_llm_answer(db, q, a),
    )

    assert result.status == STATUS_READY
    assert llm.calls == 0  # the cache answered it, no LLM needed
    assert browser._find("e3")["value"] == "Because the mission resonates."
    assert browser.submitted is False


async def test_llm_answer_is_recorded_as_suggestion():
    db = _session()
    browser = FakeBrowser(_form_snapshot())
    llm = ScriptedLLM([{"action": "fill", "ref": "e3", "value": "A generated answer."}])
    profile = get_profile()

    result = await run_agent(
        browser,
        adapter=Adapter(),
        profile=profile,
        profile_summary=build_profile_summary(profile),
        job_title="SWE Intern",
        company="Acme",
        resume_path="/tmp/resume.pdf",
        cover_letter_path=None,
        apply_url=None,
        llm_call=llm,
        caps=CAPS,
        screenshots_dir="/tmp/agent_runs/bank2",
        on_action=lambda e: None,
        answer_lookup=lambda q: answer_bank.lookup(db, q),
        answer_record=lambda q, a: answer_bank.record_llm_answer(db, q, a),
    )

    assert result.status == STATUS_READY
    assert llm.calls == 1
    entry = db.query(AnswerBankEntry).filter(
        AnswerBankEntry.question_norm == answer_bank.normalize_question("Why do you want to work here?")
    ).one()
    assert entry.answer == "A generated answer."
    assert entry.approved is False
    assert entry.source == AnswerSource.llm
