"""Pure, code-enforced safety predicates for the application agent.

These functions are the non-negotiable half of the safety invariants (§0):
they are called by the browser click helper (so a hijacked/confused LLM is
*physically* unable to submit) and by action validation. No I/O, no LLM - just
string matching - so they are cheap to call on every action and trivial to
unit-test.
"""

import re

from app.config import (
    FINAL_ACTION_BLOCKLIST,
    SENSITIVE_FIELD_PATTERNS,
    SUBMIT_BLOCKLIST,
)

_WS_RE = re.compile(r"\s+")
# Keep letters/numbers/spaces; drop punctuation so "Submit!" and "Submit"
# and "submit_application" all normalize to comparable forms.
_PUNCT_RE = re.compile(r"[^a-z0-9\s]+")


def normalize(text: str | None) -> str:
    """Lowercase, replace punctuation/underscores with spaces, and collapse
    whitespace. Used for all fuzzy substring matching below."""
    if not text:
        return ""
    lowered = text.lower().replace("_", " ")
    stripped = _PUNCT_RE.sub(" ", lowered)
    return _WS_RE.sub(" ", stripped).strip()


def contains_phrase(haystack_norm: str, phrase_norm: str) -> bool:
    """Whole-word phrase match on already-normalized strings. Padding both
    sides with spaces means `phrase` must appear as complete space-delimited
    words - so "state" matches "home state" but NOT "statement", avoiding the
    substring false positives that plague raw `in` matching on form labels."""
    if not phrase_norm:
        return False
    return f" {phrase_norm} " in f" {haystack_norm} "


def _matches_any(text: str | None, patterns: list[str]) -> str | None:
    """Return the first pattern that appears as whole words in `text`, else
    None. Both sides are normalized so matching is case/punctuation
    insensitive."""
    haystack = normalize(text)
    if not haystack:
        return None
    for pattern in patterns:
        if contains_phrase(haystack, normalize(pattern)):
            return pattern
    return None


def is_blocklisted_click(text: str | None, *, allow_apply_entry: bool = False) -> bool:
    """True if clicking an element with this accessible text/value could submit
    the application. Enforced on EVERY LLM-driven click.

    `allow_apply_entry=True` is used ONLY by the adapter's deterministic
    get_apply_entry to click the button that *opens* the form; it relaxes only
    the FINAL_ACTION_BLOCKLIST ("apply now"), never the unconditional
    SUBMIT_BLOCKLIST.
    """
    if _matches_any(text, SUBMIT_BLOCKLIST) is not None:
        return True
    if not allow_apply_entry and _matches_any(text, FINAL_ACTION_BLOCKLIST) is not None:
        return True
    return False


def blocklisted_reason(text: str | None, *, allow_apply_entry: bool = False) -> str | None:
    """The specific blocklist phrase that would reject this click, for logging.
    None if the click is allowed."""
    hit = _matches_any(text, SUBMIT_BLOCKLIST)
    if hit is not None:
        return hit
    if not allow_apply_entry:
        return _matches_any(text, FINAL_ACTION_BLOCKLIST)
    return None


def is_sensitive_field(*fragments: str | None) -> bool:
    """True if any of the given field descriptors (label, name, type, ...)
    matches a sensitive pattern the agent must never fill (password, ssn,
    salary expectation, payment, ...). Salary/comp is treated as sensitive so
    the agent PAUSEs rather than guessing a number."""
    return any(_matches_any(fragment, SENSITIVE_FIELD_PATTERNS) is not None for fragment in fragments)


def sensitive_reason(*fragments: str | None) -> str | None:
    """The specific sensitive pattern matched, for logging/PAUSE reasons."""
    for fragment in fragments:
        hit = _matches_any(fragment, SENSITIVE_FIELD_PATTERNS)
        if hit is not None:
            return hit
    return None
