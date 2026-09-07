"""Named LLM prompt constants for the application agent (§6).

Kept out of the loop so the exact wording of the safety rules is auditable in
one place. Untrusted page content (field labels, option text) flows into the
user message, so the system prompt re-states the hard rules the code also
enforces - defense in depth.
"""

AGENT_SYSTEM = (
    "You are a careful assistant filling out a job application form on behalf "
    "of a candidate. You decide the SINGLE next action to take on the current "
    "form step. You are strictly bounded by these rules:\n"
    "1. NEVER submit the application. Never choose a click whose target text "
    "means submit/send/finish/complete/apply-now. Stop at the review step.\n"
    "2. Answer ONLY from the candidate data provided in this message. NEVER "
    "invent, guess, or infer an answer that is not directly supported by that "
    "data. If a required field cannot be answered from the data, pause.\n"
    "3. Never enter passwords, SSNs, salary expectations, or payment details. "
    "If the form demands one, pause.\n"
    "4. If you see a login/sign-up wall, a CAPTCHA, or an email-verification "
    "step, pause immediately with the matching reason.\n"
    "5. For equal-opportunity (gender/race/veteran/disability) questions, do "
    "not answer here - those are handled deterministically; if one reaches "
    "you, pause.\n"
    "6. Prefer selecting an existing option (by its exact text) over free text "
    "when a field has options."
)

AGENT_SCHEMA_HINT = (
    '{"action": "fill|select|check|click|upload|step_done|review_reached|pause", '
    '"ref": "<element ref, for fill/select/check/click/upload>", '
    '"value": "<text for fill; exact option text for select; true/false for '
    'check; file path for upload>", '
    '"reason": "<login_required|captcha|unmapped_required_field|error, for pause>"}'
)


def _format_fields(fields: list[dict]) -> str:
    if not fields:
        return "(none - all fields on this step are already filled)"
    lines = []
    for el in fields:
        opts = el.get("options") or []
        opt_str = f" options={opts}" if opts else ""
        req = " REQUIRED" if el.get("required") else ""
        lines.append(
            f"- ref={el.get('ref')} label={el.get('label')!r} "
            f"type={el.get('type')}{req}{opt_str}"
        )
    return "\n".join(lines)


def _format_buttons(buttons: list[dict]) -> str:
    if not buttons:
        return "(none)"
    return "\n".join(
        f"- ref={b.get('ref')} text={b.get('label') or b.get('value')!r}" for b in buttons
    )


def agent_user(
    *,
    job_title: str,
    company: str,
    ats_hints: str,
    profile_summary: str,
    standard_answers: dict,
    unresolved_fields: list[dict],
    buttons: list[dict],
    review_candidate: bool,
) -> str:
    """Build the per-decision user message. `unresolved_fields` are only the
    fields the deterministic mapper could not resolve (never EEO/sensitive).
    `review_candidate` is True when the adapter thinks this looks like the
    review step."""
    review_note = (
        "This step appears to be the final REVIEW step (all required fields "
        "filled, a submit button is present). If you agree, respond with "
        'action "review_reached". '
        if review_candidate
        else "This does not yet look like the review step. "
    )
    return (
        f"Job: {job_title} at {company}\n\n"
        f"ATS notes: {ats_hints}\n\n"
        f"Candidate profile:\n{profile_summary}\n\n"
        f"Standard answers: {standard_answers}\n\n"
        f"Unresolved fields on this step (already-mapped fields were filled "
        f"for you):\n{_format_fields(unresolved_fields)}\n\n"
        f"Buttons available (for step_done/advancing; NEVER pick a submit "
        f"button):\n{_format_buttons(buttons)}\n\n"
        f"{review_note}"
        "Choose exactly ONE next action. If an unresolved REQUIRED field has "
        "no supporting data, pause with reason unmapped_required_field. If all "
        "fields on this step are filled and there is a next/continue button, "
        'respond "step_done".'
    )
