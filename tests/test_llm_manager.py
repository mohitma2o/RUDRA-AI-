import asyncio
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
