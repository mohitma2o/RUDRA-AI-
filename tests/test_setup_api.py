import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

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


def test_websocket_requires_authentication_and_a_local_origin():
    client = TestClient(app)
    origin = "http://127.0.0.1:5173"

    with client.websocket_connect("/ws/voice", headers={"Origin": origin}) as websocket:
        websocket.send_json({"type": "auth", "token": _API_TOKEN})
        assert websocket.receive_json() == {"type": "state", "state": "idle"}

    with client.websocket_connect("/ws/voice", headers={"Origin": "null"}) as websocket:
        websocket.send_json({"type": "auth", "token": _API_TOKEN})
        assert websocket.receive_json() == {"type": "state", "state": "idle"}

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/voice", headers={"Origin": origin}) as websocket:
            websocket.send_json({"type": "auth", "token": "invalid"})
            websocket.receive_json()

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/ws/voice",
            headers={"Origin": "https://example.com"},
        ):
            pass


def test_cors_preflight_allows_only_local_app_origins():
    client = TestClient(app)
    allowed = client.options(
        "/api/documents/notes/1",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    rejected = client.options(
        "/api/documents/notes/1",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert "access-control-allow-origin" not in rejected.headers

    file_origin = client.options(
        "/api/documents/notes",
        headers={
            "Origin": "null",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert file_origin.status_code == 200
    assert file_origin.headers["access-control-allow-origin"] == "null"
