"""Hard unit tests for the deterministic mapper (§3). Uses the example profile
loaded by app.profile.get_profile (eeo_defaults all 'decline';
work_authorization 'U.S. Citizen'; requires_sponsorship False;
willing_to_relocate True)."""

from app.agent import mapping
from app.agent.types import (
    ACTION_FILL,
    ACTION_SELECT,
    ACTION_UPLOAD,
)
from app.profile import get_profile


def _greenhouse_snapshot() -> list[dict]:
    return [
        {"ref": "e1", "role": "textbox", "type": "text", "label": "First Name", "name": "first_name", "required": True, "value": ""},
        {"ref": "e2", "role": "textbox", "type": "text", "label": "Last Name", "name": "last_name", "required": True, "value": ""},
        {"ref": "e3", "role": "textbox", "type": "email", "label": "Email", "name": "email", "required": True, "value": ""},
        {"ref": "e4", "role": "textbox", "type": "tel", "label": "Phone", "name": "phone", "required": True, "value": ""},
        {"ref": "e5", "role": "textbox", "type": "url", "label": "LinkedIn Profile", "name": "linkedin", "required": False, "value": ""},
        {"ref": "e6", "role": "textbox", "type": "text", "label": "School", "name": "school", "required": True, "value": ""},
        {"ref": "e7", "role": "combobox", "type": "select", "label": "Are you legally authorized to work in the US?", "name": "work_auth", "options": ["Yes", "No"], "required": True, "value": ""},
        {"ref": "e8", "role": "combobox", "type": "select", "label": "Will you require visa sponsorship?", "name": "sponsorship", "options": ["Yes", "No"], "required": True, "value": ""},
        {"ref": "e9", "role": "combobox", "type": "select", "label": "Are you willing to relocate?", "name": "relocate", "options": ["Yes", "No"], "required": False, "value": ""},
        {"ref": "e10", "role": "combobox", "type": "select", "label": "Gender", "name": "gender", "options": ["Male", "Female", "Decline To Self Identify"], "required": False, "value": ""},
        {"ref": "e11", "role": "combobox", "type": "select", "label": "Veteran Status", "name": "veteran", "options": ["I am a veteran", "I am not a veteran", "I don't wish to answer"], "required": False, "value": ""},
        {"ref": "e12", "role": "button", "type": "file", "label": "Resume/CV", "name": "resume", "required": True, "value": ""},
        # Unmapped free-text required question -> LLM territory.
        {"ref": "e13", "role": "textbox", "type": "textarea", "label": "Why do you want to work here?", "name": "cover_q", "required": True, "value": ""},
        # Sensitive required field -> must pause.
        {"ref": "e14", "role": "textbox", "type": "text", "label": "Desired Salary", "name": "salary", "required": True, "value": ""},
        # A submit button the mapper must ignore entirely.
        {"ref": "e15", "role": "button", "type": "submit", "label": "Submit Application", "value": ""},
    ]


def _actions_by_ref(result) -> dict[str, dict]:
    return {a["ref"]: a for a in result.actions}


def test_maps_basic_text_fields():
    profile = get_profile()
    result = mapping.map_fields(_greenhouse_snapshot(), profile, resume_path="/tmp/resume.pdf")
    by_ref = _actions_by_ref(result)

    assert by_ref["e1"] == {"action": ACTION_FILL, "ref": "e1", "value": "Jordan"}
    assert by_ref["e2"]["value"] == "Example"
    assert by_ref["e3"]["value"] == str(profile.personal.email)
    assert by_ref["e4"]["value"] == profile.personal.phone
    assert by_ref["e5"]["value"] == profile.personal.linkedin
    assert by_ref["e6"]["value"] == profile.education[0].school


def test_maps_boolean_and_auth_selects():
    profile = get_profile()
    result = mapping.map_fields(_greenhouse_snapshot(), profile, resume_path="/tmp/resume.pdf")
    by_ref = _actions_by_ref(result)

    # work authorization is a string ("U.S. Citizen") but options are Yes/No;
    # it can't be matched to an option -> falls through to unresolved.
    assert "e7" not in by_ref
    # requires_sponsorship False -> "No"
    assert by_ref["e8"] == {"action": ACTION_SELECT, "ref": "e8", "value": "No"}
    # willing_to_relocate True -> "Yes"
    assert by_ref["e9"]["value"] == "Yes"


def test_eeo_answered_only_from_defaults_as_decline():
    profile = get_profile()
    result = mapping.map_fields(_greenhouse_snapshot(), profile, resume_path="/tmp/resume.pdf")
    by_ref = _actions_by_ref(result)

    # eeo_defaults are all "decline" -> pick the decline-to-answer option.
    assert by_ref["e10"] == {"action": ACTION_SELECT, "ref": "e10", "value": "Decline To Self Identify"}
    assert by_ref["e11"]["value"] == "I don't wish to answer"


def test_resume_upload_mapped():
    profile = get_profile()
    result = mapping.map_fields(_greenhouse_snapshot(), profile, resume_path="/tmp/resume.pdf")
    by_ref = _actions_by_ref(result)
    assert by_ref["e12"] == {"action": ACTION_UPLOAD, "ref": "e12", "value": "/tmp/resume.pdf"}


def test_unmapped_required_field_is_unresolved():
    profile = get_profile()
    result = mapping.map_fields(_greenhouse_snapshot(), profile, resume_path="/tmp/resume.pdf")
    unresolved_refs = {e["ref"] for e in result.unresolved}
    assert "e13" in unresolved_refs
    # The submit button is never a field.
    assert "e15" not in unresolved_refs


def test_required_sensitive_field_forces_pause():
    profile = get_profile()
    result = mapping.map_fields(_greenhouse_snapshot(), profile, resume_path="/tmp/resume.pdf")
    pause_refs = {p["ref"] for p in result.must_pause}
    assert "e14" in pause_refs
    # It must not be filled and must not be handed to the LLM.
    assert "e14" not in {a["ref"] for a in result.actions}
    assert "e14" not in {e["ref"] for e in result.unresolved}


def test_high_resolution_rate():
    profile = get_profile()
    snapshot = _greenhouse_snapshot()
    result = mapping.map_fields(snapshot, profile, resume_path="/tmp/resume.pdf")
    # 12 fillable fields (e1-e12); e7 (work auth Yes/No) and e13/e14 aside.
    # Deterministic actions should resolve the large majority with zero LLM.
    fillable = [
        e for e in snapshot
        if e["ref"] not in {"e15"} and e["role"] != "button" or e["type"] == "file"
    ]
    assert len(result.actions) >= 0.75 * len([e for e in fillable if e["ref"] != "e14"])


def test_does_not_overwrite_prefilled_fields():
    profile = get_profile()
    snapshot = _greenhouse_snapshot()
    snapshot[0]["value"] = "AlreadyThere"  # e1 first name pre-filled
    result = mapping.map_fields(snapshot, profile, resume_path="/tmp/resume.pdf")
    assert "e1" not in {a["ref"] for a in result.actions}


def test_detect_concept():
    assert mapping.detect_concept({"label": "Mobile Number", "name": "mobile"}) == "phone"
    assert mapping.detect_concept({"label": "University", "name": "uni"}) == "school"
    assert mapping.detect_concept({"label": "First Name", "name": "fn"}) == "first_name"
    assert mapping.detect_concept({"label": "Totally Custom Question", "name": "q"}) is None


def test_whole_word_matching_avoids_substring_false_positives():
    # Regression: "Applicant Privacy Statement" must NOT match the `state`
    # concept ("state" is a substring of "statement"). Found on a live
    # Greenhouse form where it tried to type the state into a consent checkbox.
    assert mapping.detect_concept({"label": "Applicant Privacy Statement", "name": "q_123"}) is None
    # But a real state field still maps.
    assert mapping.detect_concept({"label": "Home State", "name": "state"}) == "state"


def test_string_concept_never_fills_a_checkbox():
    profile = get_profile()
    snapshot = [
        # A required consent checkbox whose label happens to contain "state".
        {"ref": "e1", "role": "checkbox", "type": "checkbox", "label": "I accept the Privacy Statement", "name": "consent", "required": True, "value": ""},
    ]
    result = mapping.map_fields(snapshot, profile)
    # No fill action produced against the checkbox.
    assert all(a["ref"] != "e1" or a["action"] != ACTION_FILL for a in result.actions)


def test_maps_address_zip_country():
    profile = get_profile()
    snapshot = [
        {"ref": "a1", "role": "textbox", "type": "text", "label": "Street Address", "name": "address", "required": False, "value": ""},
        {"ref": "a2", "role": "textbox", "type": "text", "label": "Zip Code", "name": "zip", "required": False, "value": ""},
        {"ref": "a3", "role": "textbox", "type": "text", "label": "Country", "name": "country", "required": False, "value": ""},
    ]
    by_ref = _actions_by_ref(mapping.map_fields(snapshot, profile))
    assert by_ref["a1"] == {"action": ACTION_FILL, "ref": "a1", "value": profile.personal.address}
    assert by_ref["a2"]["value"] == profile.personal.zip
    assert by_ref["a3"]["value"] == profile.personal.country


def test_choose_option_word_subset_matches_longer_wording():
    # A natural free-text veteran default resolves to a form's longer option,
    # where an inserted "protected" defeats a plain substring match.
    options = [
        "I identify as one or more classifications of a protected veteran",
        "I am not a protected veteran",
        "I don't wish to answer",
    ]
    assert mapping._choose_option(options, "not a veteran") == "I am not a protected veteran"


def test_choose_option_word_subset_respects_negation():
    # Must never pick an affirmative option for a negative answer: "I am a
    # protected veteran" lacks the "not" word, so nothing matches -> None
    # (the EEO branch then safely pauses rather than guessing).
    options = ["I am a protected veteran", "I don't wish to answer"]
    assert mapping._choose_option(options, "not a veteran") is None
