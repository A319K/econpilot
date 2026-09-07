from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_stats_returns_expected_top_level_shape():
    response = client.get("/stats")
    assert response.status_code == 200
    body = response.json()

    for key in ("internship", "full_time", "all"):
        assert key in body
        section = body[key]
        assert "counts_by_status" in section
        assert "submitted_per_day" in section
        assert "funnel" in section
        assert "avg_hours_to_submit" in section
        assert "top_companies" in section
        assert set(section["funnel"].keys()) == {
            "submitted",
            "oa",
            "interview",
            "offer",
            "conversion_rates",
        }
