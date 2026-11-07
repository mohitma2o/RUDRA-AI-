import asyncio
import json

from backend.app import main, paths


def test_legacy_user_model_setting_is_used_as_voice_model(monkeypatch, tmp_path):
    resources = tmp_path / "resources"
    defaults = resources / "rudra" / "config.json"
    defaults.parent.mkdir(parents=True)
    defaults.write_text(
        json.dumps({"ollama_model": "default-model", "ollama_voice_model": "voice-model"}),
        encoding="utf-8",
    )

    user_data = tmp_path / "user-data"
    user_data.mkdir()
    (user_data / "config.json").write_text(
        json.dumps({"ollama_model": "legacy-user-model"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(paths, "resource_dir", lambda: resources)
    monkeypatch.setattr(paths, "data_dir", lambda: user_data)

    assert main._load_config()["ollama_voice_model"] == "legacy-user-model"


def test_cancelled_turn_does_not_send_stale_idle_state(monkeypatch):
    async def blocked_turn(**_):
        await asyncio.Event().wait()

    monkeypatch.setattr(main, "run_turn", blocked_turn)
    session = main.Session(None)
    messages = []

    async def send_json(message):
        messages.append(message)

    session.send_json = send_json

    async def run():
        await session.start_turn("hello", "en")
        await session.interrupt()
        await asyncio.sleep(0)

    asyncio.run(run())
    states = [message["state"] for message in messages if message["type"] == "state"]
    assert states == ["listening", "thinking", "listening"]
