"""Coverage for PUT /profile — the dashboard's Profile page save path."""

import pytest
import yaml
from fastapi.testclient import TestClient

import app.profile as profile_module
from app.main import app

client = TestClient(app)


@pytest.fixture
def temp_profile(tmp_path, monkeypatch):
    """Point the profile module at a throwaway path so tests never touch the
    developer's real profile.yaml."""
    target = tmp_path / "profile.yaml"
    monkeypatch.setattr(profile_module, "PROFILE_PATH", target)
    profile_module.get_profile.cache_clear()
    yield target
    profile_module.get_profile.cache_clear()


def _payload():
    body = client.get("/profile").json()
    body.pop("is_placeholder", None)
    return body


def test_put_writes_yaml_and_updates_reads(temp_profile):
    payload = _payload()
    payload["personal"]["name"] = "Dana Econ"

    response = client.put("/profile", json=payload)
    assert response.status_code == 200
    assert response.json()["personal"]["name"] == "Dana Econ"

    # It landed on disk as real YAML...
    assert temp_profile.exists()
    assert yaml.safe_load(temp_profile.read_text())["personal"]["name"] == "Dana Econ"

    # ...and the lru_cache on get_profile was invalidated, so the next read is
    # the new value rather than the stale one.
    assert client.get("/profile").json()["personal"]["name"] == "Dana Econ"


def test_placeholder_flag_flips_once_saved(temp_profile):
    assert client.get("/profile").json()["is_placeholder"] is True
    assert client.put("/profile", json=_payload()).status_code == 200
    assert client.get("/profile").json()["is_placeholder"] is False


def test_invalid_payload_is_rejected_and_leaves_no_file(temp_profile):
    payload = _payload()
    payload["personal"]["email"] = "definitely-not-an-email"

    assert client.put("/profile", json=payload).status_code == 422
    assert not temp_profile.exists()


def test_save_leaves_no_temp_files_behind(temp_profile):
    client.put("/profile", json=_payload())
    assert list(temp_profile.parent.glob(".profile.*.tmp")) == []


def test_eeo_defaults_round_trip(temp_profile):
    payload = _payload()
    payload["eeo_defaults"] = {
        "gender": "decline",
        "ethnicity": "decline",
        "veteran": "no",
        "disability": "decline",
    }

    assert client.put("/profile", json=payload).status_code == 200
    assert client.get("/profile").json()["eeo_defaults"]["veteran"] == "no"
