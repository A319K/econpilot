from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"


def test_profile_omits_eeo_defaults():
    response = client.get("/profile")
    assert response.status_code == 200
    assert "eeo_defaults" not in response.json()


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
