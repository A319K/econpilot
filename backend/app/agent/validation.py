"""Structural + safety validation of a single agent action against the current
snapshot. Every action - whether produced by the deterministic mapper or the
LLM - passes through validate_action before it is executed. An invalid action
gets one corrective retry in the loop, then the run PAUSEs (§4)."""

from dataclasses import dataclass

from app.agent import safety
from app.agent.types import (
    ALL_ACTIONS,
    REF_ACTIONS,
    VALUE_ACTIONS,
    ACTION_CHECK,
    ACTION_CLICK,
    ACTION_PAUSE,
    Snapshot,
    element_descriptors,
    find_element,
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    error: str | None = None

    def __bool__(self) -> bool:  # pragma: no cover - convenience
        return self.ok


_OK = ValidationResult(True)


def validate_action(action: object, snapshot: Snapshot) -> ValidationResult:
    """Return a ValidationResult for a proposed action.

    Rejects: malformed shapes, unknown action names, pause without a reason,
    element actions whose ref is missing from the snapshot, blocklisted clicks
    (submit guard), writes into sensitive fields, and empty values where a
    value is required.
    """
    if not isinstance(action, dict):
        return ValidationResult(False, "action must be an object")

    name = action.get("action")
    if name not in ALL_ACTIONS:
        return ValidationResult(False, f"unknown action {name!r}")

    if name == ACTION_PAUSE:
        if not action.get("reason"):
            return ValidationResult(False, "pause action requires a reason")
        return _OK

    if name not in REF_ACTIONS:
        # step_done / review_reached: no element, nothing more to check.
        return _OK

    ref = action.get("ref")
    if not isinstance(ref, str) or not ref:
        return ValidationResult(False, "action requires a string ref")

    element = find_element(snapshot, ref)
    if element is None:
        return ValidationResult(False, f"ref {ref!r} not found in snapshot")

    if name == ACTION_CLICK:
        text = action.get("value") or element.get("label") or element.get("name")
        if safety.is_blocklisted_click(text):
            hit = safety.blocklisted_reason(text)
            return ValidationResult(False, f"blocklisted click (matched {hit!r})")
        return _OK

    # fill / select / check / upload write into a field: never a sensitive one.
    if safety.is_sensitive_field(*element_descriptors(element)):
        hit = safety.sensitive_reason(*element_descriptors(element))
        return ValidationResult(False, f"refusing to write to sensitive field (matched {hit!r})")

    if name in VALUE_ACTIONS:
        value = action.get("value")
        if value is None or (isinstance(value, str) and not value.strip()):
            return ValidationResult(False, f"{name} action requires a non-empty value")

    if name == ACTION_CHECK:
        # check accepts an optional boolean value; default is to check (True).
        value = action.get("value", True)
        if not isinstance(value, bool):
            return ValidationResult(False, "check value must be a boolean")

    return _OK
