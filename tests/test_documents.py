import asyncio
import time

from fastapi.testclient import TestClient

from backend.app import main
from app import documents
from app.tools import registry

document_service = documents.service
document_store = documents.storage
document_api = documents.api


def test_chunking_preserves_text_and_bounds_chunk_size():
    text = "a" * 6001 + "\nsecond paragraph\n" + "b" * 7000

    chunks = documents._chunk_text(text)

    assert "".join(chunks) == text
    assert all(len(chunk) <= documents.CHUNK_SIZE_CHARS for chunk in chunks)


def test_text_extraction_rejects_empty_and_overlarge_documents(tmp_path):
    empty = tmp_path / "empty.txt"
    empty.write_text(" \n", encoding="utf-8")
    large = tmp_path / "large.txt"
    large.write_text("x" * (documents.MAX_EXTRACTED_CHARS + 1), encoding="utf-8")

    try:
        documents._extract_document(empty)
        raise AssertionError("Expected empty-document validation.")
    except ValueError as exc:
        assert "No readable text" in str(exc)

    try:
        documents._extract_document(large)
        raise AssertionError("Expected extracted-text size validation.")
    except ValueError as exc:
        assert "character processing limit" in str(exc)


def test_document_job_map_reduces_and_persists_note(monkeypatch, tmp_path):
    monkeypatch.setattr(document_store, "data_dir", lambda: tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("x" * 12_001, encoding="utf-8")
    job_id = "job-map-reduce"
    documents._create_job(job_id, "source.txt")
    calls = []

    async def summarize(text, model, *, style="brief", language="same", instructions=None, reduce=False):
        calls.append((text, model, style, language, instructions, reduce))
        return "combined summary" if reduce else f"section {len(calls)}"

    monkeypatch.setattr(document_service, "_document_model", lambda: "doc-model")
    monkeypatch.setattr(document_service, "_summarize_text", summarize)

    asyncio.run(documents._run_job(job_id, source, "source.txt"))

    job = documents._get_job(job_id)
    notes = documents._list_notes()
    assert job["status"] == "completed"
    assert job["progress"] == 100
    assert job["summary"] == "combined summary"
    assert job["note_id"] == notes[0]["id"]
    assert notes[0]["title"] == "source"
    assert calls[-1][1:] == ("doc-model", "brief", "same", None, True)
    assert not source.exists()


def test_document_job_failure_is_persisted_and_upload_is_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(document_store, "data_dir", lambda: tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("Document contents.", encoding="utf-8")
    job_id = "job-failed"
    documents._create_job(job_id, "source.txt")

    async def fail_summary(_text, _model, *, style="brief", language="same", instructions=None, reduce=False):
        raise RuntimeError("Ollama is unavailable.")

    monkeypatch.setattr(document_service, "_document_model", lambda: "doc-model")
    monkeypatch.setattr(document_service, "_summarize_text", fail_summary)

    asyncio.run(documents._run_job(job_id, source, "source.txt"))

    job = documents._get_job(job_id)
    assert job["status"] == "failed"
    assert job["error"] == "Ollama is unavailable."
    assert not source.exists()


def test_document_job_cancellation_is_persisted_and_upload_is_removed(monkeypatch, tmp_path):
    monkeypatch.setattr(document_store, "data_dir", lambda: tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("Document contents.", encoding="utf-8")
    job_id = "job-cancelled"
    documents._create_job(job_id, "source.txt")
    summary_started = asyncio.Event()

    async def wait_for_cancellation(_text, _model, *, style="brief", language="same", instructions=None, reduce=False):
        summary_started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(document_service, "_document_model", lambda: "doc-model")
    monkeypatch.setattr(document_service, "_summarize_text", wait_for_cancellation)

    async def cancel_job():
        task = asyncio.create_task(documents._run_job(job_id, source, "source.txt"))
        await asyncio.wait_for(summary_started.wait(), timeout=1)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(cancel_job())

    job = documents._get_job(job_id)
    assert job["status"] == "cancelled"
    assert not source.exists()


def test_voice_document_summary_uses_allowlisted_file_and_saves_note(monkeypatch, tmp_path):
    allowed_root = tmp_path / "Documents"
    allowed_root.mkdir()
    source = allowed_root / "report.txt"
    source.write_text("A document that should be summarized.", encoding="utf-8")
    monkeypatch.setattr(document_service, "data_dir", lambda: tmp_path / "user-data")
    monkeypatch.setattr(document_store, "data_dir", lambda: tmp_path / "user-data")
    monkeypatch.setattr(registry, "ALLOWED_FILE_ROOTS", [allowed_root])

    async def summarize(_text, _model, *, style="brief", language="same", instructions=None, reduce=False):
        assert not reduce
        return "Voice summary"

    monkeypatch.setattr(document_service, "_document_model", lambda: "doc-model")
    monkeypatch.setattr(document_service, "_summarize_text", summarize)

    async def invoke_voice_tool():
        result = await documents.summarize_document("report.txt")
        job_id, task = next(iter(document_service._ACTIVE_JOBS.items()))
        await task
        return result, job_id

    result, job_id = asyncio.run(invoke_voice_tool())

    assert result == "Summarizing report.txt, I'll show it in the workspace."
    assert documents._get_job(job_id)["status"] == "completed"
    assert documents._list_notes()[0]["summary"] == "Voice summary"


def test_document_routes_require_token_and_stream_job_progress(monkeypatch, tmp_path):
    monkeypatch.setattr(document_store, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(document_api, "data_dir", lambda: tmp_path)

    async def no_startup():
        return None

    async def no_shutdown():
        return None

    async def finish_job(job_id, source_path, _filename, **_kwargs):
        await asyncio.sleep(0)
        document_service._update_job(job_id, "completed", 100, "Done.")
        if source_path is not None:
            source_path.unlink(missing_ok=True)

    monkeypatch.setattr(main, "_startup", no_startup)
    monkeypatch.setattr(main, "_shutdown", no_shutdown)
    monkeypatch.setattr(document_service, "_run_job", finish_job)
    headers = {"Authorization": f"Bearer {main._API_TOKEN}"}

    with TestClient(main.app) as client:
        unauthorized = client.get("/api/documents/notes")
        assert unauthorized.status_code == 401

        rejected = client.post(
            "/api/documents/jobs",
            headers=headers,
            files={"file": ("unsupported.exe", b"no", "application/octet-stream")},
        )
        assert rejected.status_code == 415

        created = client.post(
            "/api/documents/jobs",
            headers=headers,
            files={"file": ("notes.txt", b"Document contents.", "text/plain")},
        )
        assert created.status_code == 202
        job_url = created.json()["status_url"]

        job = None
        for _ in range(50):
            job = client.get(job_url, headers=headers).json()
            if job["status"] == "completed":
                break
            time.sleep(0.01)
        assert job["status"] == "completed"

        events = client.get(f"{job_url}/events", headers=headers)
        assert "event: progress" in events.text
        assert '"status": "completed"' in events.text


def test_document_note_edit_delete_and_export(monkeypatch, tmp_path):
    monkeypatch.setattr(document_store, "data_dir", lambda: tmp_path)
    note_id = documents._create_note("Initial title", "input.txt", "Key points")
    headers = {"Authorization": f"Bearer {main._API_TOKEN}"}

    with TestClient(main.app) as client:
        updated = client.patch(
            f"/api/documents/notes/{note_id}",
            headers=headers,
            json={"title": "Updated title"},
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Updated title"

        exported = client.get(
            f"/api/documents/notes/{note_id}/export?format=markdown",
            headers=headers,
        )
        assert exported.status_code == 200
        assert exported.text.startswith("# Updated title")

        deleted = client.delete(f"/api/documents/notes/{note_id}", headers=headers)
        assert deleted.status_code == 204
        assert client.get(f"/api/documents/notes/{note_id}", headers=headers).status_code == 404
