"""Adapter interface + generic snapshot helpers shared by all ATS adapters.

An adapter injects ATS-specific quirks without the loop needing to know which
provider it's on: how to enter the form (get_apply_entry), what to tell the LLM
(step_hints), how to advance a multi-step flow (next_button_ref), and how to
recognize the final review screen (is_review_step).
"""

from app.agent import safety
from app.agent.types import Element, Snapshot

# Snapshot roles/types that represent a clickable button-like control.
_BUTTON_ROLES = {"button", "link"}
_BUTTON_TYPES = {"submit", "button"}

# Text that advances a multi-step flow (never a final submit - those are
# blocklisted and filtered out).
_NEXT_KEYWORDS = ["save and continue", "next", "continue", "review", "proceed"]
# Text on the button that opens the application form.
_APPLY_KEYWORDS = ["apply for this job", "apply for this position", "apply manually", "apply"]


def is_button(element: Element) -> bool:
    role = safety.normalize(element.get("role"))
    etype = safety.normalize(element.get("type"))
    return role in _BUTTON_ROLES or etype in _BUTTON_TYPES


def button_text(element: Element) -> str:
    return element.get("label") or element.get("value") or element.get("name") or ""


def buttons(snapshot: Snapshot) -> list[Element]:
    return [el for el in snapshot if is_button(el)]


def find_button(snapshot: Snapshot, keywords: list[str]) -> Element | None:
    """First button whose text contains any keyword (checked in the given
    priority order). Blocklisted (submit) buttons are never returned."""
    for keyword in keywords:
        norm_kw = safety.normalize(keyword)
        for el in buttons(snapshot):
            text = button_text(el)
            if safety.is_blocklisted_click(text):
                continue
            if norm_kw in safety.normalize(text):
                return el
    return None


def has_blocklisted_submit(snapshot: Snapshot) -> bool:
    """True if a final-submit button is present on the page."""
    return any(safety.is_blocklisted_click(button_text(el)) for el in buttons(snapshot))


def empty_required_fields(snapshot: Snapshot) -> list[Element]:
    out: list[Element] = []
    for el in snapshot:
        if is_button(el):
            continue
        if el.get("required") and not str(el.get("value") or "").strip():
            out.append(el)
    return out


class Adapter:
    """Base adapter with a generic implementation. Subclasses override the
    parts that differ per ATS."""

    name: str = "generic"

    def step_hints(self) -> str:
        return (
            "Generic application form. Fill visible fields from the provided "
            "data. If a step has a next/continue button, advance with step_done "
            "once all its fields are filled."
        )

    def entry_keywords(self) -> list[str]:
        return _APPLY_KEYWORDS

    async def get_apply_entry(self, browser) -> bool:
        """Find and click the button that opens the application form. Returns
        True if an entry button was clicked, False if none was found (assume we
        are already on the form). Uses the entry-click exemption so an "Apply"
        button is clickable even though "apply now" is otherwise blocked."""
        snapshot = await browser.snapshot()
        entry = find_button(snapshot, self.entry_keywords())
        if entry is None:
            return False
        await browser.click(entry["ref"], allow_apply_entry=True)
        return True

    def next_button_ref(self, snapshot: Snapshot) -> str | None:
        el = find_button(snapshot, _NEXT_KEYWORDS)
        return el["ref"] if el else None

    def is_review_step(self, snapshot: Snapshot) -> bool:
        """Generic review detection: a final submit button is present AND no
        required field is still empty."""
        return has_blocklisted_submit(snapshot) and not empty_required_fields(snapshot)
