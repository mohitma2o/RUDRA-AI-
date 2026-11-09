import pytest
import httpx
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.app import main as backend_main
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


def test_gemini_key_endpoint_requires_auth_and_saves_without_returning_key(monkeypatch):
    saved_config = {}
    configured_keys = []
    monkeypatch.setattr(
        backend_main,
        "save_user_config",
        lambda updates: saved_config.update(updates),
    )
    monkeypatch.setattr(
        backend_main._llm_manager,
        "set_api_key",
        lambda key: configured_keys.append(key),
    )

    client = TestClient(app)
    missing_auth = client.post(
        "/api/settings/gemini-key",
        json={"api_key": "test-gemini-key"},
    )
    response = client.post(
        "/api/settings/gemini-key",
        headers={"Authorization": f"Bearer {_API_TOKEN}"},
        json={"api_key": "  test-gemini-key  "},
    )

    assert missing_auth.status_code == 401
    assert response.status_code == 200
    assert response.json() == {"configured": True}
    assert "test-gemini-key" not in response.text
    assert saved_config == {"gemini_api_key": "test-gemini-key"}
    assert configured_keys == ["test-gemini-key"]


def test_gemini_key_endpoint_rejects_short_keys():
    client = TestClient(
        app,
        headers={"Authorization": f"Bearer {_API_TOKEN}"},
    )
    response = client.post(
        "/api/settings/gemini-key",
        json={"api_key": "short"},
    )

    assert response.status_code == 422
    assert "6 to 512" in response.json()["detail"]


@pytest.mark.parametrize(
    ("hour", "language", "expected_language", "expected_text"),
    [
        (8, "auto", "en", "Namaskar! Good morning."),
        (14, "en", "en", "Good afternoon."),
        (20, "hi", "hi", "शुभ संध्या"),
        (9, "pa", "pa", "ਸ਼ੁਭ ਸਵੇਰ"),
    ],
)
def test_startup_greeting_is_time_and_language_aware(
    hour,
    language,
    expected_language,
    expected_text,
    monkeypatch,
):
    monkeypatch.setattr(
        backend_main,
        "_llm_manager",
        type("CloudManager", (), {"mode": "CLOUD"})(),
    )
    text, detected_language = backend_main._startup_greeting_text(hour, language)

    assert detected_language == expected_language
    assert expected_text in text
    assert "Gemini Cloud Mode" in text
    assert "online" in text.lower() or expected_language in {"hi", "pa"}


def test_authenticated_websocket_sends_startup_greeting_to_hud(monkeypatch):
    async def healthy_ollama():
        return {
            "reachable": True,
            "voice_model": "qwen2.5:1.5b",
            "voice_model_installed": True,
            "doc_model": "qwen2.5:3b-instruct-q4_K_M",
            "doc_model_installed": True,
            "models_installed": ["qwen2.5:1.5b"],
            "hardware_profile": None,
            "error": None,
        }

    async def no_audio(_text, _voice, _language):
        return b"", "audio/mpeg"

    monkeypatch.setattr(backend_main, "_startup_greeting_sent", False)
    monkeypatch.setattr(backend_main, "ollama_health", healthy_ollama)
    monkeypatch.setattr(backend_main, "synth", no_audio)
    monkeypatch.setattr(
        backend_main,
        "_llm_manager",
        type("CloudManager", (), {"mode": "CLOUD", "gemini_configured": True})(),
    )

    with TestClient(app).websocket_connect(
        "/ws/voice",
        headers={"Origin": "http://127.0.0.1:5173"},
    ) as websocket:
        websocket.send_json({"type": "auth", "token": _API_TOKEN})
        assert websocket.receive_json()["type"] == "config"
        assert websocket.receive_json()["type"] == "state"
        messages = []
        for _ in range(4):
            message = websocket.receive_json()
            messages.append(message)
            if message["type"] == "llm_status" and any(
                item["type"] == "reply_delta" for item in messages
            ):
                break
        greeting = next(item for item in messages if item["type"] == "reply_delta")
        assert greeting["text"].startswith("Namaskar!")
        assert "Gemini Cloud Mode" in greeting["text"]
        assert any(item["type"] == "llm_status" for item in messages)


@pytest.mark.parametrize(
    ("ollama_result", "expected_reachable", "voice_installed", "doc_installed", "error"),
    [
        ({"models": [{"name": "qwen2.5:1.5b"}, {"name": "qwen2.5:3b-instruct-q4_K_M"}]}, True, True, True, None),
        (httpx.ConnectError("offline"), False, False, False, "Ollama is not running or is not reachable."),
        ({"models": [{"name": "qwen2.5:1.5b"}]}, True, True, False, None),
        (httpx.Response(500, request=httpx.Request("GET", "http://ollama/api/tags")), False, False, False, "Ollama returned HTTP 500."),
    ],
)
def test_setup_status_reports_mocked_ollama(
    monkeypatch, ollama_result, expected_reachable, voice_installed, doc_installed, error
):
    class FakeClient:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, url):
            if url.endswith("/api/tags"):
                if isinstance(ollama_result, Exception):
                    raise ollama_result
                if isinstance(ollama_result, httpx.Response):
                    ollama_result.raise_for_status()
                    return ollama_result
                return httpx.Response(
                    200,
                    json=ollama_result,
                    request=httpx.Request("GET", url),
                )
            return httpx.Response(200, request=httpx.Request("GET", url))

    async def no_startup():
        return None

    async def no_shutdown():
        return None

    monkeypatch.setattr(backend_main, "_startup", no_startup)
    monkeypatch.setattr(backend_main, "_shutdown", no_shutdown)
    monkeypatch.setattr(backend_main.httpx, "AsyncClient", FakeClient)
    with TestClient(app) as client:
        response = client.get(
            "/api/setup/status",
            headers={"Authorization": f"Bearer {_API_TOKEN}"},
        )

    assert response.status_code == 200
    status = response.json()
    assert status["ollama_running"] is expected_reachable
    assert status["voice_model_installed"] is voice_installed
    assert status["doc_model_installed"] is doc_installed
    assert status["error"] == error


def test_websocket_requires_authentication_and_a_local_origin(monkeypatch):
    client = TestClient(app)
    origin = "http://127.0.0.1:5173"

    async def no_audio(_text, _voice, _language):
        return b"", "audio/mpeg"

    async def healthy_ollama():
        return {
            "reachable": True,
            "voice_model": "qwen2.5:1.5b",
            "voice_model_installed": True,
            "doc_model": "qwen2.5:3b-instruct-q4_K_M",
            "doc_model_installed": True,
            "models_installed": ["qwen2.5:1.5b", "phi3:mini"],
            "hardware_profile": {
                "tier": "low",
                "ram_gb": 8.0,
                "recommended_models": ["qwen2.5:1.5b", "phi3:mini"],
                "basis": "System RAM only; GPU VRAM is not detected.",
            },
            "error": None,
        }

    monkeypatch.setattr(backend_main, "ollama_health", healthy_ollama)
    monkeypatch.setattr(backend_main, "_startup_greeting_sent", True)
    monkeypatch.setattr(backend_main, "synth", no_audio)
    assert backend_main._websocket_origin_allowed(origin)
    assert backend_main._websocket_origin_allowed("null")
    assert not backend_main._websocket_origin_allowed("https://example.com")

    with client.websocket_connect("/ws/voice", headers={"Origin": origin}) as websocket:
        websocket.send_json({"type": "auth", "token": _API_TOKEN})
        assert websocket.receive_json()["type"] == "config"
        assert websocket.receive_json() == {"type": "state", "state": "idle"}
        messages = []
        while True:
            message = websocket.receive_json()
            messages.append(message)
            if message["type"] == "llm_status":
                break
        llm_status = next(message for message in messages if message["type"] == "llm_status")
        assert llm_status["type"] == "llm_status"
        assert llm_status["models_installed"] == ["qwen2.5:1.5b", "phi3:mini"]
        assert llm_status["hardware_profile"]["tier"] == "low"

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/voice", headers={"Origin": origin}) as websocket:
            websocket.send_json({"type": "auth", "token": "invalid"})
            websocket.receive_json()


def test_packaged_websocket_accepts_file_origin_and_missing_origin(monkeypatch):
    monkeypatch.setattr(backend_main, "_IS_DEV", False)
    monkeypatch.setattr(backend_main, "_ALLOWED_ORIGINS", ("file://", "null"))
    assert backend_main._websocket_origin_allowed("file://")
    assert backend_main._websocket_origin_allowed("null")
    assert backend_main._websocket_origin_allowed(None)
    assert not backend_main._websocket_origin_allowed("https://example.com")

    async def healthy_ollama():
        return {
            "reachable": False,
            "voice_model": "qwen2.5:1.5b",
            "voice_model_installed": False,
            "doc_model": "qwen2.5:3b-instruct-q4_K_M",
            "doc_model_installed": False,
            "error": "Ollama is not running.",
        }

    monkeypatch.setattr(backend_main, "ollama_health", healthy_ollama)
    monkeypatch.setattr(backend_main, "_startup_greeting_sent", True)
    client = TestClient(app)
    for headers in ({"Origin": "file://"}, {}):
        with client.websocket_connect("/ws/voice", headers=headers) as websocket:
            websocket.send_json({"type": "auth", "token": _API_TOKEN})
            assert websocket.receive_json()["type"] == "config"
            assert websocket.receive_json()["type"] == "state"
            for _ in range(5):
                if websocket.receive_json()["type"] == "llm_status":
                    break
            else:
                raise AssertionError("Initial LLM status was not sent.")


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
