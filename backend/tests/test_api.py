from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


def test_profile_exposes_eeo_defaults_for_editing():
    """EEO defaults are part of the profile the dashboard edits.

    JobPilot deliberately omitted these from /profile (data minimisation — the
    dashboard only ever displayed the profile, so demographics never needed to
    cross the API boundary). EconPilot's Profile page *edits* profile.yaml, so
    they have to round-trip: our users are non-technical and must not be sent
    to a text editor for the one section covering race, disability and veteran
    status. Still localhost-only, single-user, and already on the user's disk.
    """
    response = client.get("/profile")
    assert response.status_code == 200
    assert "eeo_defaults" in response.json()


def test_profile_reports_placeholder_state():
    body = client.get("/profile").json()
    assert isinstance(body["is_placeholder"], bool)


def test_company_crud():
    create_resp = client.post("/companies", json={"name": "Acme", "is_target": True})
    assert create_resp.status_code == 201
    company_id = create_resp.json()["id"]

    get_resp = client.get(f"/companies/{company_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Acme"

    list_resp = client.get("/companies")
    assert list_resp.status_code == 200
    assert any(c["id"] == company_id for c in list_resp.json())

    patch_resp = client.patch(f"/companies/{company_id}", json={"notes": "updated"})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["notes"] == "updated"

    delete_resp = client.delete(f"/companies/{company_id}")
    assert delete_resp.status_code == 204

    missing_resp = client.get(f"/companies/{company_id}")
    assert missing_resp.status_code == 404
