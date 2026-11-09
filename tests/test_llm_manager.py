import asyncio
import time
from types import SimpleNamespace

from backend.app import llm_manager


def test_hardware_profile_selects_ram_tier(monkeypatch):
    for ram_gb, expected in ((8, "low"), (16, "mid"), (32, "high")):
        monkeypatch.setattr(
            llm_manager.psutil,
            "virtual_memory",
            lambda ram_gb=ram_gb: SimpleNamespace(total=ram_gb * 1024 ** 3),
        )
        profile = llm_manager.LLMManager.hardware_profile()
        assert profile["tier"] == expected
        assert profile["ram_gb"] == ram_gb
        assert profile["recommended_models"]
        assert "GPU VRAM" in profile["basis"]


def test_installed_models_are_discovered_from_ollama(monkeypatch):
    class FakeClient:
        def __init__(self, timeout):
            assert timeout == 3

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, url):
            assert url == "http://ollama:11434/api/tags"
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {
                    "models": [
                        {"name": "qwen2.5:1.5b"},
                        {"name": "phi3:mini"},
                        {"invalid": True},
                    ]
                },
            )

    monkeypatch.setattr(llm_manager.httpx, "AsyncClient", FakeClient)
    manager = llm_manager.LLMManager("http://ollama:11434/")

    assert asyncio.run(manager.get_installed_models()) == ["qwen2.5:1.5b", "phi3:mini"]


def test_gemini_response_uses_flash_and_conversation_history():
    calls = {}

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.update(kwargs)
            return SimpleNamespace(text="Hello from Gemini.")

    client = SimpleNamespace(models=FakeModels())
    manager = llm_manager.LLMManager("http://ollama:11434", api_key="test-key")
    manager._gemini_client = client
    result = asyncio.run(
        manager.generate_response(
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
                {"role": "user", "content": "How are you?"},
            ],
            "Be brief.",
        )
    )

    assert manager.gemini_configured
    assert result == "Hello from Gemini."
    assert calls["model"] == llm_manager.GEMINI_MODEL == "gemini-2.5-flash"
    assert [item["role"] for item in calls["contents"]] == ["user", "model", "user"]
    assert calls["config"].system_instruction == "Be brief."


def test_gemini_manager_answers_creator_query_without_network_or_api_key():
    manager = llm_manager.LLMManager("http://ollama:11434")
    response = asyncio.run(
        manager.generate_response(
            [{"role": "user", "content": "Who made you?"}],
            "Be brief.",
        )
    )

    assert "Mohit Mattoo" in response


def test_setting_empty_gemini_key_disables_cloud():
    manager = llm_manager.LLMManager("http://ollama:11434", api_key="test-key")

    manager.set_api_key(" ")

    assert not manager.gemini_configured


def test_new_manager_defaults_to_cloud_even_without_api_key():
    manager = llm_manager.LLMManager("http://ollama:11434")

    assert manager.mode == "CLOUD"
    assert not manager.gemini_configured


def test_gemini_api_key_validation_precedes_cloud_initialization():
    manager = llm_manager.LLMManager(
        "http://ollama:11434",
        api_key="short",
        mode="CLOUD",
    )

    assert not manager.gemini_configured
    assert manager.mode == "CLOUD"
    assert not manager.is_valid_api_key("short")
    assert manager.is_valid_api_key("valid-key")
    try:
        manager.set_api_key("short")
    except ValueError as error:
        assert "6 to 512" in str(error)
    else:
        raise AssertionError("Short Gemini API keys must be rejected.")


def test_engine_mode_switch_requires_key_and_checks_local_ollama(monkeypatch):
    manager = llm_manager.LLMManager("http://ollama:11434")

    async def run():
        success, message = await manager.switch_mode("CLOUD")
        assert not success
        assert "API key is missing" in message
        assert manager.mode == "CLOUD"

        async def ollama_unavailable():
            raise llm_manager.httpx.ConnectError("offline")

        monkeypatch.setattr(manager, "get_installed_models", ollama_unavailable)
        success, message = await manager.switch_mode("LOCAL")
        assert not success
        assert "within 3 seconds" in message
        assert manager.mode == "CLOUD"

        async def ollama_available():
            return ["qwen2.5:1.5b"]

        monkeypatch.setattr(manager, "get_installed_models", ollama_available)
        success, message = await manager.switch_mode("LOCAL")
        assert success
        assert "Local Ollama" in message
        assert manager.mode == "LOCAL"

        manager.set_api_key("test-key")
        success, message = await manager.switch_mode("CLOUD")
        assert success
        assert "Gemini Cloud" in message
        assert manager.mode == "CLOUD"

    asyncio.run(run())


def test_local_mode_heartbeat_stops_after_three_seconds(monkeypatch):
    manager = llm_manager.LLMManager("http://ollama:11434")

    async def stalled_ollama():
        await asyncio.sleep(10)

    monkeypatch.setattr(manager, "get_installed_models", stalled_ollama)
    started = time.monotonic()
    success, message = asyncio.run(manager.switch_mode("LOCAL"))
    elapsed = time.monotonic() - started

    assert not success
    assert "within 3 seconds" in message
    assert manager.mode == "CLOUD"
    assert elapsed < 3.5


def test_gemini_circuit_breaker_preserves_selected_mode():
    manager = llm_manager.LLMManager(
        "http://ollama:11434",
        api_key="valid-key",
        mode="CLOUD",
    )
    calls = []

    def failed_request(_history, _system_prompt):
        calls.append(True)
        raise RuntimeError("network unavailable")

    manager._generate_gemini_response = failed_request

    async def run():
        for _ in range(llm_manager.GEMINI_FAILURE_THRESHOLD):
            try:
                await manager.generate_response([], "Be brief.")
            except llm_manager.GeminiUnavailableError:
                pass
            else:
                raise AssertionError("Failed Gemini requests must be reported.")

        try:
            await manager.generate_response([], "Be brief.")
        except llm_manager.GeminiUnavailableError as error:
            assert "temporarily paused" in str(error)
        else:
            raise AssertionError("The open circuit must reject requests.")

    asyncio.run(run())
    assert len(calls) == llm_manager.GEMINI_FAILURE_THRESHOLD
    assert manager.mode == "CLOUD"


def test_image_analysis_uses_installed_local_vision_model(monkeypatch):
    manager = llm_manager.LLMManager("http://ollama:11434")
    calls = []

    async def installed_models():
        return ["qwen2.5:1.5b", "qwen2.5vl:3b"]

    async def chat(model, prompt, image=None):
        calls.append((model, prompt, image))
        return "A settings window is open."

    monkeypatch.setattr(manager, "get_installed_models", installed_models)
    monkeypatch.setattr(manager, "_chat", chat)

    result = asyncio.run(manager.analyze_image(b"image-bytes", "English"))

    assert result == "A settings window is open."
    assert calls[0][0] == "qwen2.5vl:3b"
    assert "untrusted" in calls[0][1]
    assert calls[0][2] == "aW1hZ2UtYnl0ZXM="


def test_image_analysis_reports_missing_vision_model():
    manager = llm_manager.LLMManager("http://ollama:11434")

    async def installed_models():
        return ["qwen2.5:1.5b"]

    manager.get_installed_models = installed_models

    try:
        asyncio.run(manager.analyze_image(b"image-bytes", "English"))
    except RuntimeError as error:
        assert "ollama pull qwen2.5vl:3b" in str(error)
    else:
        raise AssertionError("Image analysis must require an installed vision model.")
