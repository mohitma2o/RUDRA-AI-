from fastapi.testclient import TestClient

from backend.app.main import _API_TOKEN, app


def test_setup_status_requires_local_api_token():
    client = TestClient(app)

    missing = client.get("/api/setup/status")
    invalid = client.get(
        "/api/setup/status",
        headers={"Authorization": "Bearer invalid-token"},
    )
    pull = client.post("/api/setup/pull-model")

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert pull.status_code == 401
    assert _API_TOKEN
