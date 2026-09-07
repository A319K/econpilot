"""Shared, JSON-serializable data shapes for the agent.

Elements and actions are plain dicts (not dataclasses) so they drop straight
into the AgentRun.action_log JSON column and are trivial to construct in tests
and in the browser snapshot extractor.
"""

from typing import Any, TypedDict

# --- snapshot elements ----------------------------------------------------


class Element(TypedDict, total=False):
    ref: str  # stable per-run reference (e.g. "e7")
    role: str  # accessibility role: textbox, combobox, checkbox, radio, button...
    label: str  # accessible label / name shown to the user
    name: str  # DOM name attribute (for synonym matching)
    autocomplete: str  # HTML autocomplete token (e.g. "given-name", "tel")
    type: str  # input type or control kind: text, email, select, file, checkbox...
    options: list[str]  # choices for select / radio group / checkbox group
    required: bool
    value: str  # current value ("" when empty)


Snapshot = list[Element]


def find_element(snapshot: Snapshot, ref: str) -> Element | None:
    for el in snapshot:
        if el.get("ref") == ref:
            return el
    return None


def element_descriptors(el: Element) -> list[str]:
    """The strings used for label/name/type matching (mapper + safety)."""
    return [el.get("label", ""), el.get("name", ""), el.get("type", "")]


# --- actions --------------------------------------------------------------

ACTION_FILL = "fill"
ACTION_SELECT = "select"
ACTION_CHECK = "check"
ACTION_CLICK = "click"
ACTION_UPLOAD = "upload"
ACTION_PAUSE = "pause"
ACTION_STEP_DONE = "step_done"
ACTION_REVIEW_REACHED = "review_reached"

# Actions that operate on a specific element and therefore require a ref.
REF_ACTIONS = {ACTION_FILL, ACTION_SELECT, ACTION_CHECK, ACTION_CLICK, ACTION_UPLOAD}
# Actions that require a non-empty value.
VALUE_ACTIONS = {ACTION_FILL, ACTION_SELECT, ACTION_UPLOAD}
# Control-flow actions the LLM may emit that touch no element.
CONTROL_ACTIONS = {ACTION_PAUSE, ACTION_STEP_DONE, ACTION_REVIEW_REACHED}
ALL_ACTIONS = REF_ACTIONS | CONTROL_ACTIONS


def make_action(action: str, ref: str | None = None, value: Any = None, **extra: Any) -> dict:
    out: dict = {"action": action}
    if ref is not None:
        out["ref"] = ref
    if value is not None:
        out["value"] = value
    out.update(extra)
    return out
