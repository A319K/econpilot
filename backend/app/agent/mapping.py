"""Deterministic field mapping - the zero-LLM first pass (§3).

Given a page snapshot and the profile, resolve as many fields as possible by
matching each field's label/name/autocomplete against the synonym table, then
producing concrete fill/select/check/upload actions from profile data. Whatever
is left over is returned for the LLM loop to attempt; fields that must never be
answered by the LLM (sensitive fields, EEO with no default/decline option) are
returned as forced pauses.

This module is pure (no browser, no LLM, no DB) so it can be hammered in unit
tests. Target: 80%+ of a typical Greenhouse form resolved here.
"""

from dataclasses import dataclass, field

from app.agent import safety
from app.agent.types import (
    ACTION_CHECK,
    ACTION_FILL,
    ACTION_SELECT,
    ACTION_UPLOAD,
    Element,
    Snapshot,
    make_action,
)
from app.config import DECLINE_OPTION_PATTERNS, FIELD_SYNONYMS
from app.profile import Profile

# Concepts answered from profile.eeo_defaults ONLY (§0). They never go to the
# LLM: if they can't be resolved deterministically the run pauses.
EEO_CONCEPTS = {"gender", "ethnicity", "veteran", "disability"}
# Concepts that map to a boolean standard answer (rendered as yes/no options).
BOOLEAN_CONCEPTS = {"requires_sponsorship", "willing_to_relocate"}
# Concepts backed by a file upload rather than a text/select value.
FILE_CONCEPTS = {"resume", "cover_letter"}

# Filler words dropped before the word-subset option match in _choose_option, so
# a default like "not a veteran" is compared on {not, veteran}. Negation words
# ("no", "not") are deliberately kept - they carry the meaning of the answer.
_OPTION_STOPWORDS = {"i", "a", "am", "is", "are", "an", "the", "to", "of", "and", "or", "my", "as"}


@dataclass
class MappingResult:
    # Ready-to-execute actions produced entirely from profile data.
    actions: list[dict] = field(default_factory=list)
    # Fields the mapper couldn't resolve but the LLM may safely attempt.
    unresolved: list[Element] = field(default_factory=list)
    # Fields that must halt the run: (element, reason). Reasons align with
    # AgentRun pause reasons (unmapped_required_field) but carry detail.
    must_pause: list[dict] = field(default_factory=list)


def _match_text(element: Element) -> str:
    return safety.normalize(
        " ".join(
            [
                element.get("label", ""),
                element.get("name", ""),
                element.get("autocomplete", ""),
            ]
        )
    )


def detect_concept(element: Element) -> str | None:
    """Return the profile concept this field maps to, or None. Concepts are
    checked in FIELD_SYNONYMS insertion order (most specific first, e.g.
    first_name before full_name) and the first hit wins."""
    haystack = _match_text(element)
    if not haystack:
        return None
    for concept, fragments in FIELD_SYNONYMS.items():
        for fragment in fragments:
            if safety.contains_phrase(haystack, safety.normalize(fragment)):
                return concept
    return None


def _bool_to_yesno(value: bool) -> str:
    return "yes" if value else "no"


def _choose_option(options: list[str], desired: str, *, decline: bool = False) -> str | None:
    """Pick the option best matching `desired`. When decline=True, or `desired`
    is itself a decline word, prefer a 'prefer not to answer' option."""
    norm_desired = safety.normalize(desired)
    want_decline = decline or any(
        safety.contains_phrase(norm_desired, safety.normalize(p)) for p in DECLINE_OPTION_PATTERNS
    )

    if want_decline:
        for option in options:
            norm_opt = safety.normalize(option)
            if any(safety.contains_phrase(norm_opt, safety.normalize(p)) for p in DECLINE_OPTION_PATTERNS):
                return option
        if decline:
            return None  # explicit decline requested but no decline option

    for option in options:
        norm_opt = safety.normalize(option)
        if not norm_opt:
            continue
        if norm_opt == norm_desired or norm_desired in norm_opt or norm_opt in norm_desired:
            return option

    # Fallback: pick an option that contains every significant word of the
    # desired answer (ignoring filler words). This lets a natural free-text
    # default like "not a veteran" resolve to a form's longer "I am not a
    # protected veteran" option, where the inserted "protected" defeats a plain
    # substring match. Requiring *all* significant words keeps it conservative
    # (an affirmative "I am a protected veteran" lacks "not", so it won't match).
    desired_words = [w for w in norm_desired.split() if w not in _OPTION_STOPWORDS]
    if desired_words:
        for option in options:
            opt_words = set(safety.normalize(option).split())
            if all(w in opt_words for w in desired_words):
                return option
    return None


def _string_value(concept: str, profile: Profile) -> str | None:
    p = profile.personal
    edu = profile.education[0] if profile.education else None
    sa = profile.standard_answers

    name_parts = p.name.split()
    values: dict[str, str | None] = {
        "first_name": name_parts[0] if name_parts else None,
        "last_name": name_parts[-1] if len(name_parts) > 1 else None,
        "full_name": p.name,
        "email": str(p.email),
        "phone": p.phone,
        "address": p.address,
        "city": p.city,
        "state": p.state,
        "zip": p.zip,
        "country": p.country,
        "linkedin": p.linkedin,
        "github": p.github,
        "website": p.website,
        "school": edu.school if edu else None,
        "degree": edu.degree if edu else None,
        "major": edu.major if edu else None,
        "gpa": str(edu.gpa) if edu and edu.gpa is not None else None,
        "graduation_date": sa.graduation_date,
        "work_authorization": sa.work_authorization,
    }
    return values.get(concept)


def _resolve_field(
    element: Element,
    profile: Profile,
    resume_path: str | None,
    cover_letter_path: str | None,
    result: MappingResult,
) -> bool:
    """Try to resolve one element. Returns True if it was handled (added to
    actions or must_pause), False if it should fall through to `unresolved`."""
    ref = element["ref"]
    descriptors = [element.get("label", ""), element.get("name", ""), element.get("type", "")]

    # Sensitive fields are never filled. A required one blocks the form -> pause.
    if safety.is_sensitive_field(*descriptors):
        hit = safety.sensitive_reason(*descriptors)
        if element.get("required"):
            result.must_pause.append(
                {"ref": ref, "reason": f"required sensitive field ({hit})", "field": element.get("label")}
            )
            return True
        return True  # optional sensitive field: silently skip, never fill

    concept = detect_concept(element)
    if concept is None:
        return False

    options = element.get("options") or []
    etype = safety.normalize(element.get("type"))

    # File uploads (resume / cover letter).
    if concept in FILE_CONCEPTS:
        path = resume_path if concept == "resume" else cover_letter_path
        if path:
            result.actions.append(make_action(ACTION_UPLOAD, ref=ref, value=path))
            return True
        return False  # no PDF available -> let the loop decide (may pause if required)

    # EEO: answered ONLY from eeo_defaults; decline when no default; else pause.
    if concept in EEO_CONCEPTS:
        default = getattr(profile.eeo_defaults, concept)
        if options:
            chosen = _choose_option(options, default or "", decline=not default)
            if chosen is not None:
                result.actions.append(make_action(ACTION_SELECT, ref=ref, value=chosen))
                return True
        elif default:
            result.actions.append(make_action(ACTION_FILL, ref=ref, value=default))
            return True
        # Could not honor the EEO field from defaults/decline -> pause (never LLM).
        result.must_pause.append(
            {"ref": ref, "reason": f"EEO field with no usable default/decline option ({concept})", "field": element.get("label")}
        )
        return True

    # Boolean standard answers (sponsorship, relocation).
    if concept in BOOLEAN_CONCEPTS:
        flag = getattr(profile.standard_answers, concept)
        if options:
            chosen = _choose_option(options, _bool_to_yesno(flag))
            if chosen is not None:
                result.actions.append(make_action(ACTION_SELECT, ref=ref, value=chosen))
                return True
            return False
        if etype == "checkbox":
            result.actions.append(make_action(ACTION_CHECK, ref=ref, value=bool(flag)))
            return True
        result.actions.append(make_action(ACTION_FILL, ref=ref, value=_bool_to_yesno(flag)))
        return True

    # Plain string-valued concepts.
    value = _string_value(concept, profile)
    if value is None:
        return False

    if options:
        chosen = _choose_option(options, value)
        if chosen is not None:
            result.actions.append(make_action(ACTION_SELECT, ref=ref, value=chosen))
            return True
        return False  # can't match value to an option -> let LLM try

    # A string value can only be typed into a text-like control. If the concept
    # somehow lands on a checkbox/radio (with no options), don't fill it - defer
    # so it isn't mis-typed.
    if etype in {"checkbox", "radio"}:
        return False

    result.actions.append(make_action(ACTION_FILL, ref=ref, value=value))
    return True


# Roles/types that are not fillable fields (buttons, links, static text). The
# mapper ignores these entirely; clicks are the loop's/adapter's job.
_NON_FIELD_ROLES = {"button", "link", "heading", "img", "text", "none", "presentation"}
_NON_FIELD_TYPES = {"submit", "button", "reset", "hidden"}


def _is_field(element: Element) -> bool:
    etype = safety.normalize(element.get("type"))
    # File inputs are rendered as buttons by the snapshot extractor but ARE
    # fillable (upload) fields - let them through regardless of role.
    if etype == "file":
        return True
    role = safety.normalize(element.get("role"))
    if role in _NON_FIELD_ROLES or etype in _NON_FIELD_TYPES:
        return False
    return True


def map_fields(
    snapshot: Snapshot,
    profile: Profile,
    *,
    resume_path: str | None = None,
    cover_letter_path: str | None = None,
) -> MappingResult:
    """Deterministically resolve as many snapshot fields as possible from the
    profile. See module docstring."""
    result = MappingResult()

    for element in snapshot:
        if not element.get("ref"):
            continue
        if not _is_field(element):
            continue
        # Don't overwrite fields that already hold a value (e.g. a prior step,
        # or a browser autofill).
        if str(element.get("value") or "").strip():
            continue

        handled = _resolve_field(element, profile, resume_path, cover_letter_path, result)
        if not handled:
            result.unresolved.append(element)

    return result
