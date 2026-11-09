import asyncio
import json
from types import SimpleNamespace

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


def test_model_update_changes_active_session_and_persists(monkeypatch):
    session = main.Session(None)
    persisted = {}
    monkeypatch.setattr(main, "save_user_config", persisted.update)

    asyncio.run(session.update_config({"llm_model": "phi3:mini"}))

    assert session.model == "phi3:mini"
    assert persisted == {"ollama_voice_model": "phi3:mini"}


def test_rejected_cloud_mode_update_reports_error_and_restores_active_mode(monkeypatch):
    session = main.Session(None)
    messages = []
    status_modes = []
    persisted = {}
    manager = SimpleNamespace(
        mode="LOCAL",
    )

    async def reject_mode(_mode):
        return False, "Gemini API key is missing."

    manager.switch_mode = reject_mode
    monkeypatch.setattr(main, "_llm_manager", manager)
    monkeypatch.setattr(main, "save_user_config", persisted.update)

    async def send_json(message):
        messages.append(message)

    async def push_llm_status():
        status_modes.append(manager.mode)

    session.send_json = send_json
    session.push_llm_status = push_llm_status

    asyncio.run(session.update_config({"engine_mode": "CLOUD"}))

    assert messages == [{
        "type": "error",
        "code": "engine_mode_unavailable",
        "message": "Gemini API key is missing.",
    }]
    assert status_modes == ["LOCAL"]
    assert persisted == {}


def test_creator_query_is_answered_without_starting_a_model_turn(monkeypatch):
    session = main.Session(None)
    replies = []
    languages = []

    async def no_interrupt():
        return None

    async def direct_reply(text, language, *, interrupt_current=True):
        replies.append(text)
        languages.append(language)

    monkeypatch.setattr(session, "interrupt", no_interrupt)
    monkeypatch.setattr(session, "speak_direct_reply", direct_reply)

    handled = asyncio.run(
        session.respond_to_creator_query(
            "Tuhanu kine banaya?",
            "en",
        )
    )

    assert handled
    assert len(replies) == 1
    assert "Mohit Mattoo" in replies[0]
    assert languages == ["pa"]
    assert session.history == [
        {"role": "user", "content": "Tuhanu kine banaya?"},
    ]


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
