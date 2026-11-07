"""Document summarization jobs, progress events, and saved notes."""

import asyncio
import json
import re
import sqlite3
import shutil
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Iterator, Optional

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from .paths import data_dir, load_config
from .tools.registry import Tier, tool

router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_EXTRACTED_CHARS = 500_000
CHUNK_SIZE_CHARS = 6_000
MAX_CHUNKS = 84
MAX_SUMMARY_TOKENS = 350
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".pptx"}
OLLAMA_CHAT_URL = "http://127.0.0.1:11434/api/chat"
_ACTIVE_JOBS: dict[str, asyncio.Task] = {}


class NoteUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@contextmanager
def _database() -> Iterator[sqlite3.Connection]:
    path = data_dir() / "documents.sqlite3"
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS document_jobs (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    summary TEXT,
                    note_id INTEGER,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS document_job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES document_jobs(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS document_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source_filename TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            yield connection
    finally:
        connection.close()


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _create_job(job_id: str, filename: str) -> None:
    now = _timestamp()
    payload = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "message": "Document queued.",
    }
    with _database() as connection:
        connection.execute(
            """
            INSERT INTO document_jobs
                (id, filename, status, progress, message, created_at, updated_at)
            VALUES (?, ?, 'queued', 0, ?, ?, ?)
            """,
            (job_id, filename, payload["message"], now, now),
        )
        connection.execute(
            """
            INSERT INTO document_job_events (job_id, event_type, payload, created_at)
            VALUES (?, 'progress', ?, ?)
            """,
            (job_id, json.dumps(payload), now),
        )


def _update_job(
    job_id: str,
    status: str,
    progress: int,
    message: str,
    *,
    summary: Optional[str] = None,
    note_id: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    now = _timestamp()
    payload: dict = {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "message": message,
    }
    if note_id is not None:
        payload["note_id"] = note_id
    if error:
        payload["error"] = error

    with _database() as connection:
        connection.execute(
            """
            UPDATE document_jobs
            SET status = ?, progress = ?, message = ?, summary = COALESCE(?, summary),
                note_id = COALESCE(?, note_id), error = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, progress, message, summary, note_id, error, now, job_id),
        )
        connection.execute(
            """
            INSERT INTO document_job_events (job_id, event_type, payload, created_at)
            VALUES (?, 'progress', ?, ?)
            """,
            (job_id, json.dumps(payload), now),
        )


def _get_job(job_id: str) -> Optional[dict]:
    with _database() as connection:
        row = connection.execute(
            "SELECT * FROM document_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return dict(row) if row else None


def _get_events_after(job_id: str, event_id: int) -> list[dict]:
    with _database() as connection:
        rows = connection.execute(
            """
            SELECT id, event_type, payload FROM document_job_events
            WHERE job_id = ? AND id > ? ORDER BY id
            """,
            (job_id, event_id),
        ).fetchall()
    return [dict(row) for row in rows]


def _create_note(title: str, filename: str, summary: str) -> int:
    now = _timestamp()
    with _database() as connection:
        cursor = connection.execute(
            """
            INSERT INTO document_notes
                (title, source_filename, summary, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, filename, summary, now, now),
        )
        return int(cursor.lastrowid)


def _list_notes() -> list[dict]:
    with _database() as connection:
        rows = connection.execute(
            "SELECT * FROM document_notes ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def _get_note(note_id: int) -> Optional[dict]:
    with _database() as connection:
        row = connection.execute(
            "SELECT * FROM document_notes WHERE id = ?",
            (note_id,),
        ).fetchone()
    return dict(row) if row else None


def _extract_document(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    elif suffix == ".pdf":
        from pypdf import PdfReader

        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    elif suffix == ".docx":
        from docx import Document

        document = Document(str(path))
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
        parts.extend(
            " | ".join(cell.text for cell in row.cells)
            for table in document.tables
            for row in table.rows
        )
        text = "\n".join(parts)
    elif suffix == ".pptx":
        from pptx import Presentation

        presentation = Presentation(str(path))
        text = "\n".join(
            shape.text
            for slide in presentation.slides
            for shape in slide.shapes
            if getattr(shape, "has_text_frame", False) and shape.text.strip()
        )
    else:
        raise ValueError(f"Unsupported document type: {suffix or '(no extension)'}")

    text = text.strip()
    if not text:
        raise ValueError("No readable text was found in the document.")
    if len(text) > MAX_EXTRACTED_CHARS:
        raise ValueError(
            f"Document text exceeds the {MAX_EXTRACTED_CHARS:,} character processing limit."
        )
    return text


def _chunk_text(text: str, max_chars: int = CHUNK_SIZE_CHARS) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for paragraph in text.splitlines(keepends=True):
        if len(paragraph) > max_chars:
            if current:
                chunks.append("".join(current))
                current = []
                current_length = 0
            chunks.extend(
                paragraph[index : index + max_chars]
                for index in range(0, len(paragraph), max_chars)
            )
            continue
        if current and current_length + len(paragraph) > max_chars:
            chunks.append("".join(current))
            current = []
            current_length = 0
        current.append(paragraph)
        current_length += len(paragraph)

    if current:
        chunks.append("".join(current))
    return chunks


def _document_model() -> str:
    config = load_config()
    return config.get(
        "ollama_doc_model",
        config.get("ollama_voice_model", config.get("ollama_model", "qwen2.5:3b-instruct-q4_K_M")),
    )


async def _summarize_text(text: str, model: str, *, reduce: bool = False) -> str:
    instruction = (
        "Combine the section summaries into one concise, faithful document summary. "
        "Remove repetition and preserve important conclusions and action items."
        if reduce
        else "Summarize this document section. Preserve key facts, names, dates, conclusions, "
        "and action items. Do not invent details."
    )
    payload = {
        "model": model,
        "stream": False,
        "keep_alive": "5m",
        "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": text},
        ],
        "options": {"num_ctx": 4096, "num_predict": MAX_SUMMARY_TOKENS},
    }
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(OLLAMA_CHAT_URL, json=payload)
        response.raise_for_status()
    result = response.json().get("message", {}).get("content", "").strip()
    if not result:
        raise RuntimeError("The document model returned an empty summary.")
    return result


async def _reduce_summaries(summaries: list[str], model: str) -> str:
    while len(summaries) > 1:
        summaries = [
            await _summarize_text(
                "\n\n".join(summaries[index : index + 6]),
                model,
                reduce=True,
            )
            for index in range(0, len(summaries), 6)
        ]
    return summaries[0]


async def _run_job(job_id: str, source_path: Path, filename: str) -> None:
    try:
        _update_job(job_id, "extracting", 5, "Extracting document text.")
        extraction = asyncio.create_task(asyncio.to_thread(_extract_document, source_path))
        try:
            text = await asyncio.shield(extraction)
        except asyncio.CancelledError:
            await asyncio.gather(extraction, return_exceptions=True)
            raise
        chunks = _chunk_text(text)
        if len(chunks) > MAX_CHUNKS:
            raise ValueError(f"Document is too large to summarize in one job ({MAX_CHUNKS} sections maximum).")

        model = _document_model()
        summaries: list[str] = []
        for index, chunk in enumerate(chunks):
            summaries.append(await _summarize_text(chunk, model))
            progress = 10 + int(75 * (index + 1) / len(chunks))
            _update_job(
                job_id,
                "summarizing",
                progress,
                f"Summarized section {index + 1} of {len(chunks)}.",
            )

        if len(summaries) > 1:
            _update_job(job_id, "summarizing", 90, "Combining section summaries.")
        summary = await _reduce_summaries(summaries, model)
        note_id = _create_note(
            Path(filename).stem,
            filename,
            summary,
        )
        _update_job(
            job_id,
            "completed",
            100,
            "Summary saved to your notes.",
            summary=summary,
            note_id=note_id,
        )
    except asyncio.CancelledError:
        _update_job(job_id, "cancelled", 0, "Document processing was cancelled.")
        raise
    except Exception as exc:
        _update_job(
            job_id,
            "failed",
            0,
            "Document processing failed.",
            error=str(exc),
        )
    finally:
        try:
            source_path.unlink(missing_ok=True)
        except OSError as exc:
            print(f"[Documents] Could not remove temporary upload {source_path}: {exc}")


@tool(
    name="summarize_document",
    description="Summarize a local document from an approved personal folder and save it to notes.",
    schema={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Document name or approved path"}},
        "required": ["name"],
    },
)
async def summarize_document(name: str) -> str:
    from .tools.files import resolve_file_reference

    source, error = resolve_file_reference(name)
    if error:
        return error
    assert source is not None
    if source.suffix.casefold() not in ALLOWED_EXTENSIONS:
        return f"Unsupported document type: {source.suffix or '(no extension)'}"
    try:
        if source.stat().st_size > MAX_UPLOAD_BYTES:
            return "The document exceeds the 25 MB processing limit."
    except OSError as exc:
        return f"Could not inspect document: {exc}"

    job_id = uuid.uuid4().hex
    upload_dir = data_dir() / "documents" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    copy_path = upload_dir / f"{job_id}{source.suffix.casefold()}"
    await asyncio.to_thread(shutil.copyfile, source, copy_path)
    try:
        await asyncio.to_thread(_create_job, job_id, source.name)
    except Exception:
        copy_path.unlink(missing_ok=True)
        raise

    await _run_job(job_id, copy_path, source.name)
    job = await asyncio.to_thread(_get_job, job_id)
    if job is None:
        raise RuntimeError("The document job disappeared before it completed.")
    if job["status"] != "completed":
        return job.get("error") or job["message"]
    return job["summary"]


@router.post("/jobs", status_code=202)
async def create_document_job(file: UploadFile = File(...)) -> dict:
    filename = Path((file.filename or "").replace("\\", "/")).name
    suffix = Path(filename).suffix.casefold()
    if len(filename) > 255:
        raise HTTPException(status_code=400, detail="The document file name is too long.")
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported document type. Use: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
        )

    contents = await file.read(MAX_UPLOAD_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded document is empty.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The document exceeds the 25 MB upload limit.")

    job_id = uuid.uuid4().hex
    upload_dir = data_dir() / "documents" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    source_path = upload_dir / f"{job_id}{suffix}"
    await asyncio.to_thread(source_path.write_bytes, contents)
    try:
        await asyncio.to_thread(_create_job, job_id, filename)
    except Exception:
        source_path.unlink(missing_ok=True)
        raise

    task = asyncio.create_task(_run_job(job_id, source_path, filename))
    _ACTIVE_JOBS[job_id] = task
    task.add_done_callback(lambda completed: _ACTIVE_JOBS.pop(job_id, None))
    return {"job_id": job_id, "status_url": f"/api/documents/jobs/{job_id}"}


@router.get("/jobs/{job_id}")
async def get_document_job(job_id: str) -> dict:
    job = await asyncio.to_thread(_get_job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Document job not found.")
    return job


@router.get("/jobs/{job_id}/events")
async def document_job_events(
    job_id: str,
    request: Request,
    after_id: int = 0,
) -> StreamingResponse:
    if await asyncio.to_thread(_get_job, job_id) is None:
        raise HTTPException(status_code=404, detail="Document job not found.")

    async def stream() -> AsyncIterator[str]:
        cursor = max(0, after_id)
        while True:
            if await request.is_disconnected():
                break
            events = await asyncio.to_thread(_get_events_after, job_id, cursor)
            for event in events:
                cursor = event["id"]
                yield (
                    f"id: {cursor}\n"
                    f"event: {event['event_type']}\n"
                    f"data: {event['payload']}\n\n"
                )
            job = await asyncio.to_thread(_get_job, job_id)
            if job is None or (job["status"] in {"completed", "failed", "cancelled"} and not events):
                break
            await asyncio.sleep(0.25)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete("/jobs/{job_id}", status_code=202)
async def cancel_document_job(job_id: str) -> dict:
    job = await asyncio.to_thread(_get_job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Document job not found.")
    if job["status"] in {"completed", "failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Document job is already finished.")
    task = _ACTIVE_JOBS.get(job_id)
    if task is not None:
        task.cancel()
    else:
        _update_job(job_id, "cancelled", 0, "Document processing was cancelled.")
    return {"job_id": job_id, "status": "cancelling"}


@router.get("/notes")
async def list_document_notes() -> dict:
    notes = await asyncio.to_thread(_list_notes)
    return {"notes": notes}


@router.get("/notes/{note_id}")
async def get_document_note(note_id: int) -> dict:
    note = await asyncio.to_thread(_get_note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Document note not found.")
    return note


@router.patch("/notes/{note_id}")
async def update_document_note(note_id: int, update: NoteUpdate) -> dict:
    title = update.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Note title cannot be blank.")
    now = _timestamp()
    with _database() as connection:
        result = connection.execute(
            "UPDATE document_notes SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, note_id),
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Document note not found.")
    return await asyncio.to_thread(_get_note, note_id)


@router.delete("/notes/{note_id}", status_code=204)
async def delete_document_note(note_id: int) -> Response:
    with _database() as connection:
        result = connection.execute("DELETE FROM document_notes WHERE id = ?", (note_id,))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Document note not found.")
    return Response(status_code=204)


@router.get("/notes/{note_id}/export")
async def export_document_note(note_id: int, format: str = "markdown") -> Response:
    note = await asyncio.to_thread(_get_note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Document note not found.")
    if format not in {"markdown", "text"}:
        raise HTTPException(status_code=422, detail="Export format must be 'markdown' or 'text'.")

    if format == "markdown":
        content = f"# {note['title']}\n\nSource: {note['source_filename']}\n\n{note['summary']}\n"
        media_type = "text/markdown; charset=utf-8"
        extension = "md"
    else:
        content = f"{note['title']}\nSource: {note['source_filename']}\n\n{note['summary']}\n"
        media_type = "text/plain; charset=utf-8"
        extension = "txt"
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", note["title"]).strip("-") or "rudra-note"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.{extension}"'},
    )


async def shutdown_document_jobs() -> None:
    tasks = list(_ACTIVE_JOBS.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
