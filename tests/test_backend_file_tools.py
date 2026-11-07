import asyncio

import pytest

from backend.app.tools import files
from backend.app.tools import registry
from backend.app.tools import applications


def test_allowed_paths_resolve_inside_roots_and_reject_escape(monkeypatch, tmp_path):
    allowed_root = tmp_path / "Documents"
    allowed_root.mkdir()
    inside = allowed_root / "notes.txt"
    inside.write_text("notes", encoding="utf-8")
    outside = tmp_path / "private.txt"
    outside.write_text("private", encoding="utf-8")
    monkeypatch.setattr(registry, "ALLOWED_FILE_ROOTS", [allowed_root])

    assert registry.resolve_allowed_path(inside) == inside.resolve()
    assert registry.resolve_allowed_path(allowed_root / ".." / outside.name) is None
    assert registry.resolve_allowed_path(outside) is None


def test_allowed_paths_reject_symlinks_that_escape_roots(monkeypatch, tmp_path):
    allowed_root = tmp_path / "Documents"
    allowed_root.mkdir()
    outside = tmp_path / "private"
    outside.mkdir()
    link = allowed_root / "shared"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Symlink creation is unavailable: {exc}")
    monkeypatch.setattr(registry, "ALLOWED_FILE_ROOTS", [allowed_root])

    assert registry.resolve_allowed_path(link / "private.txt") is None


def test_search_file_only_returns_files_inside_allowed_roots(monkeypatch, tmp_path):
    allowed_root = tmp_path / "Documents"
    allowed_root.mkdir()
    match = allowed_root / "project-report.txt"
    match.write_text("report", encoding="utf-8")
    outside = tmp_path / "outside-report.txt"
    outside.write_text("report", encoding="utf-8")
    monkeypatch.setattr(registry, "ALLOWED_FILE_ROOTS", [allowed_root])

    result = asyncio.run(files.search_file("report"))

    assert str(match.resolve()) in result
    assert str(outside.resolve()) not in result


def test_open_file_denies_paths_outside_allowed_roots(monkeypatch, tmp_path):
    allowed_root = tmp_path / "Documents"
    allowed_root.mkdir()
    outside = tmp_path / "private.txt"
    outside.write_text("private", encoding="utf-8")
    monkeypatch.setattr(registry, "ALLOWED_FILE_ROOTS", [allowed_root])

    result = asyncio.run(files.open_file(str(outside)))

    assert result.startswith("Access denied:")


def test_open_file_resolves_a_filename_from_allowed_roots(monkeypatch, tmp_path):
    allowed_root = tmp_path / "Documents"
    allowed_root.mkdir()
    target = allowed_root / "notes.txt"
    target.write_text("notes", encoding="utf-8")
    opened = []
    monkeypatch.setattr(registry, "ALLOWED_FILE_ROOTS", [allowed_root])
    monkeypatch.setattr(files, "_open_with_default_app", opened.append)

    result = asyncio.run(files.open_file("notes.txt"))

    assert result == "Opened file: notes.txt"
    assert opened == [target.resolve()]


def test_open_folder_accepts_an_allowed_folder_shortcut(monkeypatch, tmp_path):
    allowed_root = tmp_path / "Documents"
    allowed_root.mkdir()
    opened = []
    monkeypatch.setattr(registry, "ALLOWED_FILE_ROOTS", [allowed_root])
    monkeypatch.setattr(files, "_open_with_default_app", opened.append)

    result = asyncio.run(files.open_folder("my Documents"))

    assert result == f"Opened folder: {allowed_root.resolve()}"
    assert opened == [allowed_root.resolve()]


def test_read_document_is_bounded_and_restricted(monkeypatch, tmp_path):
    allowed_root = tmp_path / "Documents"
    allowed_root.mkdir()
    target = allowed_root / "report.txt"
    target.write_text("x" * (files.MAX_DOCUMENT_TEXT_CHARS + 20), encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    monkeypatch.setattr(registry, "ALLOWED_FILE_ROOTS", [allowed_root])

    content = asyncio.run(files.read_document("report.txt"))
    denied = asyncio.run(files.read_document(str(outside)))

    assert len(content) <= files.MAX_DOCUMENT_TEXT_CHARS
    assert content.endswith("[Text truncated.]")
    assert denied.startswith("Access denied:")


def test_closing_applications_requires_confirmation():
    registered = registry.REGISTRY["close_application"]

    assert registered.run is applications.close_application
    assert registered.tier is registry.Tier.CONFIRM
