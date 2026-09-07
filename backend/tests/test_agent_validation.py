from app.agent.types import make_action
from app.agent.validation import validate_action

SNAPSHOT = [
    {"ref": "e1", "role": "textbox", "type": "text", "label": "First Name", "required": True, "value": ""},
    {"ref": "e2", "role": "textbox", "type": "text", "label": "Desired Salary", "required": True, "value": ""},
    {"ref": "e3", "role": "button", "type": "submit", "label": "Submit Application", "value": ""},
    {"ref": "e4", "role": "button", "type": "button", "label": "Next", "value": ""},
    {"ref": "e5", "role": "checkbox", "type": "checkbox", "label": "Agree", "value": ""},
]


def test_valid_fill():
    assert validate_action(make_action("fill", ref="e1", value="Jordan"), SNAPSHOT).ok


def test_missing_ref_rejected():
    assert not validate_action({"action": "fill", "value": "x"}, SNAPSHOT).ok


def test_unknown_ref_rejected():
    assert not validate_action(make_action("fill", ref="nope", value="x"), SNAPSHOT).ok


def test_unknown_action_rejected():
    assert not validate_action({"action": "teleport", "ref": "e1"}, SNAPSHOT).ok


def test_blocklisted_click_rejected():
    result = validate_action(make_action("click", ref="e3"), SNAPSHOT)
    assert not result.ok
    assert "blocklisted" in result.error


def test_safe_click_allowed():
    assert validate_action(make_action("click", ref="e4"), SNAPSHOT).ok


def test_sensitive_field_write_rejected():
    result = validate_action(make_action("fill", ref="e2", value="100000"), SNAPSHOT)
    assert not result.ok
    assert "sensitive" in result.error


def test_empty_value_rejected():
    assert not validate_action(make_action("fill", ref="e1", value=""), SNAPSHOT).ok
    assert not validate_action({"action": "fill", "ref": "e1", "value": "   "}, SNAPSHOT).ok


def test_pause_requires_reason():
    assert not validate_action({"action": "pause"}, SNAPSHOT).ok
    assert validate_action({"action": "pause", "reason": "login_required"}, SNAPSHOT).ok


def test_control_actions_ok():
    assert validate_action({"action": "step_done"}, SNAPSHOT).ok
    assert validate_action({"action": "review_reached"}, SNAPSHOT).ok


def test_check_value_must_be_bool():
    assert validate_action(make_action("check", ref="e5", value=True), SNAPSHOT).ok
    assert not validate_action({"action": "check", "ref": "e5", "value": "yes"}, SNAPSHOT).ok


def test_non_dict_rejected():
    assert not validate_action("submit", SNAPSHOT).ok
