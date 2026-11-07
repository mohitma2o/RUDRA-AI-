import json

from backend.app import paths


def test_resource_dir_uses_pyinstaller_bundle_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert paths.resource_dir() == tmp_path


def test_data_dir_uses_configured_user_path_and_creates_it(monkeypatch, tmp_path):
    target = tmp_path / "Rudra Data"
    monkeypatch.setenv("RUDRA_DATA_DIR", str(target))

    assert paths.data_dir() == target
    assert target.is_dir()


def test_save_user_config_merges_existing_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("RUDRA_DATA_DIR", str(tmp_path))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"language": "hi", "stt_model": "base"}), encoding="utf-8")

    paths.save_user_config({"stt_model": "small"})

    assert json.loads(config_path.read_text(encoding="utf-8")) == {
        "language": "hi",
        "stt_model": "small",
    }
