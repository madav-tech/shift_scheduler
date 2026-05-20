from fastapi.testclient import TestClient

from shift_scheduler.main import app


def test_health_returns_ok() -> None:
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
