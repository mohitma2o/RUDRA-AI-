import sys
import threading
import types

import numpy as np

from rudra.state import AppState, state
from rudra import wakeword


def test_app_state_is_thread_safe_and_rejects_non_boolean_values():
    app_state = AppState()
    threads = [
        threading.Thread(target=lambda: setattr(app_state, "is_muted", True))
        for _ in range(10)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert app_state.is_muted is True

    try:
        app_state.is_muted = "yes"
    except TypeError:
        pass
    else:
        raise AssertionError("AppState must reject non-boolean mute values.")


def test_native_wake_loop_skips_inference_while_muted(monkeypatch):
    stop_event = threading.Event()

    class FakeStream:
        def read(self, _size, exception_on_overflow=False):
            stop_event.set()
            return np.zeros(1280, dtype=np.int16).tobytes()

        def stop_stream(self):
            pass

        def close(self):
            pass

    class FakePyAudio:
        paInt16 = 8

        def open(self, **_):
            return FakeStream()

        def terminate(self):
            pass

    class FakeModel:
        def predict(self, _audio):
            raise AssertionError("Muted audio must not be sent to wake-word inference.")

    fake_pyaudio = types.SimpleNamespace(PyAudio=FakePyAudio, paInt16=8)
    monkeypatch.setitem(sys.modules, "pyaudio", fake_pyaudio)
    monkeypatch.setattr(wakeword, "_stop_event", stop_event)
    monkeypatch.setattr(state, "is_muted", True)

    wakeword._openwakeword_loop(lambda _: None, FakeModel())


def test_fallback_wake_loop_skips_recording_while_muted(monkeypatch):
    stop_event = threading.Event()

    class FakeStream:
        def read(self, *_args, **_kwargs):
            raise AssertionError("Muted audio must not be read for transcription.")

        def stop_stream(self):
            pass

        def close(self):
            pass

    class FakePyAudio:
        paInt16 = 8

        def open(self, **_):
            return FakeStream()

        def terminate(self):
            pass

    class FakeWhisperModel:
        def __init__(self, *_args, **_kwargs):
            pass

        def transcribe(self, *_args, **_kwargs):
            raise AssertionError("Muted audio must not be transcribed.")

    monkeypatch.setitem(
        sys.modules,
        "pyaudio",
        types.SimpleNamespace(PyAudio=FakePyAudio, paInt16=8),
    )
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        types.SimpleNamespace(WhisperModel=FakeWhisperModel),
    )
    monkeypatch.setattr(wakeword, "_stop_event", stop_event)
    monkeypatch.setattr(stop_event, "wait", lambda _seconds: stop_event.set())
    monkeypatch.setattr(state, "is_muted", True)

    wakeword._speech_recognition_loop(lambda _: None)


def test_input_stream_prefers_default_microphone_and_logs_device(monkeypatch, capsys):
    class FakePyAudio:
        def __init__(self):
            self.options = None

        def get_default_input_device_info(self):
            return {"index": 4, "name": "USB microphone"}

        def open(self, **options):
            self.options = options
            return "stream"

    pa = FakePyAudio()
    pyaudio_module = types.SimpleNamespace(paInt16=8)

    result = wakeword._open_input_stream(pa, pyaudio_module, rate=16000, chunk=1280)

    assert result == "stream"
    assert pa.options["input_device_index"] == 4
    assert "USB microphone (device 4)" in capsys.readouterr().out


def test_listener_worker_retries_after_audio_errors(monkeypatch, capsys):
    stop_event = threading.Event()
    calls = []

    def broken_listener(*_):
        calls.append("retry")
        if len(calls) == 1:
            raise OSError("device disconnected")
        stop_event.set()

    monkeypatch.setattr(wakeword, "_stop_event", stop_event)
    monkeypatch.setattr(wakeword, "_LISTENER_RETRY_SECONDS", 0)
    monkeypatch.setattr(wakeword, "_speech_recognition_loop", broken_listener)

    wakeword._listener_worker(lambda _: None)

    assert len(calls) == 2
    assert "OSError: device disconnected" in capsys.readouterr().out


def test_app_state_starts_unmuted():
    assert AppState().is_muted is False
