"""Thin async browser wrapper over Playwright (§1).

Playwright is an optional dependency (the `agent` extra) and is imported lazily
inside methods so that importing this module - and therefore the whole
app.agent package and the API - works without a browser installed. Tests inject
a fake implementing the same async surface (see AgentBrowser), so nothing here
runs during the browser-free suite.

The single most important guarantee: click() checks EVERY click against the
submit blocklist and raises BlocklistedClickError, so a hijacked or confused
LLM decision is physically unable to submit the application.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from app.agent import safety
from app.agent.types import Snapshot


class BlocklistedClickError(Exception):
    """Raised when a click is refused because its target matches the submit
    blocklist. Never caught-and-retried into a different submit - it aborts the
    click permanently."""


@runtime_checkable
class AgentBrowser(Protocol):
    """The async surface the loop and adapters depend on. Both PlaywrightBrowser
    and the test fake satisfy this."""

    async def goto(self, url: str) -> None: ...
    async def snapshot(self) -> Snapshot: ...
    async def fill(self, ref: str, value: str) -> None: ...
    async def select(self, ref: str, option: str) -> None: ...
    async def check(self, ref: str, value: bool = True) -> None: ...
    async def click(self, ref: str, *, allow_apply_entry: bool = False) -> None: ...
    async def upload(self, ref: str, path: str) -> None: ...
    async def screenshot(self, path: str) -> None: ...


# JS injected into the page to extract a simplified interactive-element tree and
# tag each element with a stable per-run ref. Radios are grouped by name into a
# single synthetic field; selects expose their option texts.
_SNAPSHOT_JS = r"""
() => {
  const out = [];
  // Persist the counter on window so refs are STABLE across snapshots: an
  // element that already carries a data-agent-ref keeps it even as the form's
  // DOM mutates (fields appear/reorder). This stops the loop from re-filling
  // the same field under a drifting positional ref.
  window.__agentRefCounter = window.__agentRefCounter || 0;
  const nextRef = () => 'e' + (++window.__agentRefCounter);

  const labelFor = (el) => {
    const aria = el.getAttribute('aria-label');
    if (aria) return aria.trim();
    const labelledby = el.getAttribute('aria-labelledby');
    if (labelledby) {
      const parts = labelledby.split(/\s+/).map(id => {
        const n = document.getElementById(id);
        return n ? n.textContent.trim() : '';
      }).filter(Boolean);
      if (parts.length) return parts.join(' ');
    }
    if (el.id) {
      const lab = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (lab) return lab.textContent.trim();
    }
    const wrap = el.closest('label');
    if (wrap) return wrap.textContent.trim();
    const ph = el.getAttribute('placeholder');
    if (ph) return ph.trim();
    return '';
  };

  const isVisible = (el) => {
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 || r.height > 0 || el.type === 'file';
  };

  // Group radios by name so a set of options becomes one field.
  const seenRadioGroups = new Set();

  const controls = document.querySelectorAll(
    'input, select, textarea, button, a[href], [role="button"], [contenteditable="true"]'
  );

  controls.forEach((el) => {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || tag).toLowerCase();
    if (type === 'hidden') return;
    if (!isVisible(el)) return;

    if (tag === 'input' && type === 'radio') {
      const name = el.getAttribute('name') || '';
      if (name && seenRadioGroups.has(name)) return;
      if (name) seenRadioGroups.add(name);
      const group = name
        ? Array.from(document.querySelectorAll('input[type="radio"][name="' + CSS.escape(name) + '"]'))
        : [el];
      const existingGroup = el.getAttribute('data-agent-ref-group');
      const ref = existingGroup || nextRef();
      if (!existingGroup) group.forEach(r => r.setAttribute('data-agent-ref-group', ref));
      const checked = group.find(r => r.checked);
      out.push({
        ref, role: 'radio', type: 'radio',
        label: labelFor(el.closest('fieldset') || el) || name,
        name,
        autocomplete: el.getAttribute('autocomplete') || '',
        required: group.some(r => r.required),
        value: checked ? labelFor(checked) : '',
        options: group.map(r => labelFor(r)).filter(Boolean),
      });
      return;
    }

    const ref = el.getAttribute('data-agent-ref') || nextRef();
    el.setAttribute('data-agent-ref', ref);
    const base = {
      ref,
      name: el.getAttribute('name') || el.id || '',
      autocomplete: el.getAttribute('autocomplete') || '',
      label: labelFor(el),
      required: !!el.required || el.getAttribute('aria-required') === 'true',
    };

    if (tag === 'select') {
      const opts = Array.from(el.options).map(o => o.textContent.trim()).filter(Boolean);
      out.push({ ...base, role: 'combobox', type: 'select', options: opts,
                 value: el.value ? (el.selectedOptions[0]?.textContent.trim() || '') : '' });
    } else if (tag === 'button' || type === 'submit' || type === 'button' ||
               el.getAttribute('role') === 'button' || tag === 'a') {
      out.push({ ...base, role: tag === 'a' ? 'link' : 'button', type,
                 label: base.label || el.textContent.trim(),
                 value: el.value || '', options: [] });
    } else if (type === 'checkbox') {
      out.push({ ...base, role: 'checkbox', type: 'checkbox', options: [],
                 value: el.checked ? 'true' : '' });
    } else if (type === 'file') {
      out.push({ ...base, role: 'button', type: 'file', options: [],
                 value: (el.files && el.files.length) ? el.files[0].name : '' });
    } else {
      out.push({ ...base, role: 'textbox', type, options: [],
                 value: el.value || el.textContent || '' });
    }
  });

  return out;
}
"""


class PlaywrightBrowser:
    """Concrete AgentBrowser backed by a headed, persistent Chromium context."""

    def __init__(self, context, page) -> None:
        self._context = context
        self._page = page

    @classmethod
    async def launch(cls, user_data_dir: str, headless: bool = False) -> "PlaywrightBrowser":
        from playwright.async_api import async_playwright  # lazy

        Path(user_data_dir).mkdir(parents=True, exist_ok=True)
        pw = await async_playwright().start()
        context = await pw.chromium.launch_persistent_context(
            user_data_dir,
            headless=headless,
            args=["--no-first-run", "--no-default-browser-check"],
        )
        page = context.pages[0] if context.pages else await context.new_page()
        browser = cls(context, page)
        browser._pw = pw  # keep a handle so it isn't GC'd
        return browser

    @property
    def page(self):
        return self._page

    def _locator(self, ref: str):
        return self._page.locator(f'[data-agent-ref="{ref}"]')

    async def goto(self, url: str) -> None:
        await self._page.goto(url, wait_until="domcontentloaded")

    async def snapshot(self) -> Snapshot:
        return await self._page.evaluate(_SNAPSHOT_JS)

    async def fill(self, ref: str, value: str) -> None:
        await self._locator(ref).fill(value)

    async def select(self, ref: str, option: str) -> None:
        el = self._locator(ref)
        # Radio group: click the option whose accessible label matches.
        group = self._page.locator(f'[data-agent-ref-group="{ref}"]')
        if await group.count() > 0:
            await group.get_by_text(option, exact=False).first.check()
            return
        # Native <select>: match by visible label, falling back to value.
        try:
            await el.select_option(label=option)
        except Exception:
            await el.select_option(value=option)

    async def check(self, ref: str, value: bool = True) -> None:
        el = self._locator(ref)
        if value:
            await el.check()
        else:
            await el.uncheck()

    async def click(self, ref: str, *, allow_apply_entry: bool = False) -> None:
        # Enforce the blocklist against the element's live accessible text -
        # not a cached snapshot - so nothing can be smuggled past it.
        text = await self._accessible_text(ref)
        if safety.is_blocklisted_click(text, allow_apply_entry=allow_apply_entry):
            hit = safety.blocklisted_reason(text, allow_apply_entry=allow_apply_entry)
            raise BlocklistedClickError(
                f"refused to click ref {ref!r} (text {text!r} matched blocklist {hit!r})"
            )
        await self._locator(ref).click()

    async def upload(self, ref: str, path: str) -> None:
        await self._locator(ref).set_input_files(path)

    async def screenshot(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        await self._page.screenshot(path=path, full_page=True)

    async def close(self) -> None:
        await self._context.close()
        pw = getattr(self, "_pw", None)
        if pw is not None:
            await pw.stop()

    async def _accessible_text(self, ref: str) -> str:
        el = self._locator(ref)
        try:
            text = (await el.text_content()) or ""
            aria = (await el.get_attribute("aria-label")) or ""
            value = (await el.get_attribute("value")) or ""
        except Exception:
            return ""
        return " ".join(t for t in (text, aria, value) if t).strip()
