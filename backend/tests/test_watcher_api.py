from fastapi.testclient import TestClient

from app.main import app
from app.routers import watcher as watcher_router_module

client = TestClient(app)


def test_watcher_status_reports_disabled_by_default():
    response = client.get("/watcher/status")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["running"] is False
    assert body["last_cycle"] is None


def test_notify_test_endpoint_uses_none_adapter_by_default():
    response = client.post("/notify/test")
    assert response.status_code == 200
    body = response.json()
    assert body["adapter"] == "none"
    assert body["success"] is True


def test_watcher_run_now_returns_409_when_already_running(monkeypatch):
    class AlwaysRunningService:
        async def run_cycle(self):
            from app.watcher.scheduler import WatchCycleAlreadyRunning

            raise WatchCycleAlreadyRunning()

    monkeypatch.setattr(watcher_router_module, "get_watcher_service", lambda: AlwaysRunningService())

    response = client.post("/watcher/run-now")
    assert response.status_code == 409
