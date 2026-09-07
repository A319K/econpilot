"""Answer bank: a review-gated cache of free-text application answers (§ answer
bank feature). Sits between the deterministic mapper and the LLM - a recurring
custom question ("Why do you want to work here?", "Notice period?") is answered
from a previously-approved entry with zero LLM calls; only genuinely novel
questions reach the model, and their answers are saved as suggestions for the
human to approve.

Matching is normalized-exact first, then a fuzzy ratio to catch slightly
reworded questions. Only `approved` entries are ever reused, preserving the
never-fabricate guarantee.
"""

from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.agent import safety
from app.models.answer_bank import AnswerBankEntry, AnswerSource
from app.models.mixins import utcnow

# Fuzzy match threshold (SequenceMatcher ratio over normalized questions).
# High so only clear rewordings match; the human reviews saved answers anyway.
FUZZY_THRESHOLD = 0.9
# Below this length a fuzzy match is unreliable - require exact instead.
MIN_FUZZY_LEN = 12


def normalize_question(text: str | None) -> str:
    return safety.normalize(text)


def _best_fuzzy(
    question_norm: str, candidates: list[AnswerBankEntry]
) -> AnswerBankEntry | None:
    if len(question_norm) < MIN_FUZZY_LEN:
        return None
    best: AnswerBankEntry | None = None
    best_ratio = 0.0
    for entry in candidates:
        ratio = SequenceMatcher(None, question_norm, entry.question_norm).ratio()
        if ratio >= FUZZY_THRESHOLD and ratio > best_ratio:
            best, best_ratio = entry, ratio
    return best


def find_entry(db: Session, question: str) -> AnswerBankEntry | None:
    """Return the approved entry matching `question` (exact-normalized first,
    then fuzzy), or None. Does not mutate."""
    qn = normalize_question(question)
    if not qn:
        return None
    approved = db.query(AnswerBankEntry).filter(AnswerBankEntry.approved.is_(True))
    exact = approved.filter(AnswerBankEntry.question_norm == qn).one_or_none()
    if exact is not None:
        return exact
    return _best_fuzzy(qn, approved.all())


def lookup(db: Session, question: str) -> str | None:
    """Return a cached approved answer for `question` and record the hit
    (times_used/last_used_at). None if no approved match."""
    entry = find_entry(db, question)
    if entry is None:
        return None
    entry.times_used += 1
    entry.last_used_at = utcnow()
    db.commit()
    return entry.answer


def record_llm_answer(db: Session, question: str, answer: str) -> AnswerBankEntry | None:
    """Persist an LLM-generated answer as a suggestion (approved=False) for
    later human review. Never overwrites an existing approved entry. Returns the
    stored entry, or None for empty input."""
    qn = normalize_question(question)
    if not qn or not (answer and answer.strip()):
        return None
    existing = (
        db.query(AnswerBankEntry).filter(AnswerBankEntry.question_norm == qn).one_or_none()
    )
    if existing is not None:
        if not existing.approved:
            # Refresh the pending suggestion with the latest generation.
            existing.answer = answer
            db.commit()
        return existing
    entry = AnswerBankEntry(
        question_norm=qn,
        question_raw=question,
        answer=answer,
        source=AnswerSource.llm,
        approved=False,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
