"""Authenticated FastAPI routes for document jobs, notes, and exports."""

import asyncio
import json
import re
import uuid
from io import BytesIO
from pathlib import Path
from typing import AsyncIterator, Optional

from docx import Document
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from ..paths import data_dir
from . import service
from .storage import (
    _create_job,
    _database,
    _get_events_after,
    _get_job,
    _get_note,
    _get_note_source,
    _list_notes,
    _timestamp,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


class NoteUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class RegenerateRequest(BaseModel):
    style: str = "brief"
    language: str = "same"
    instructions: Optional[str] = Field(default=None, max_length=1000)


def _validate_note_options(style: str, language: str, instructions: Optional[str]) -> None:
    try:
        service.validate_note_options(style, language, instructions)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/jobs", status_code=202)
async def create_document_job(
    file: UploadFile = File(...),
    style: str = Form(default="brief"),
    language: str = Form(default="same"),
    instructions: Optional[str] = Form(default=None),
) -> dict:
    _validate_note_options(style, language, instructions)
    if instructions and len(instructions) > 1000:
        raise HTTPException(status_code=422, detail="Custom instructions are limited to 1,000 characters.")
    filename = Path((file.filename or "").replace("\\", "/")).name
    suffix = Path(filename).suffix.casefold()
    if len(filename) > 255:
        raise HTTPException(status_code=400, detail="The document file name is too long.")
    if suffix not in service.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported document type. Use: {', '.join(sorted(service.ALLOWED_EXTENSIONS))}.",
        )

    max_upload_bytes = service._max_upload_bytes()
    contents = await file.read(max_upload_bytes + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded document is empty.")
    if len(contents) > max_upload_bytes:
        limit_mb = service._configured_limit("documents_max_upload_mb", 25)
        raise HTTPException(status_code=413, detail=f"The document exceeds the {limit_mb} MB upload limit.")

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

    task = asyncio.create_task(
        service._run_job(
            job_id,
            source_path,
            filename,
            style=style,
            language=language,
            instructions=instructions,
        )
    )
    service._ACTIVE_JOBS[job_id] = task
    task.add_done_callback(lambda completed: service._ACTIVE_JOBS.pop(job_id, None))
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
            if job is None or (
                job["status"] in {"completed", "failed", "cancelled"} and not events
            ):
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
    task = service._ACTIVE_JOBS.get(job_id)
    if task is not None:
        task.cancel()
    else:
        from .storage import _update_job

        _update_job(job_id, "cancelled", 0, "Document processing was cancelled.")
    return {"job_id": job_id, "status": "cancelling"}


@router.get("/notes")
async def list_document_notes() -> dict:
    return {"notes": await asyncio.to_thread(_list_notes)}


@router.get("/notes/{note_id}")
async def get_document_note(note_id: int) -> dict:
    note = await asyncio.to_thread(_get_note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Document note not found.")
    return note


@router.post("/notes/{note_id}/regenerate", status_code=202)
async def regenerate_document_note(note_id: int, request: RegenerateRequest) -> dict:
    _validate_note_options(request.style, request.language, request.instructions)
    note = await asyncio.to_thread(_get_note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Document note not found.")
    source = await asyncio.to_thread(_get_note_source, note_id)
    if not source or not source["source_text"] or not source["content_hash"]:
        raise HTTPException(
            status_code=409,
            detail="The extracted source text is unavailable for this older note. Upload the document again to regenerate it.",
        )
    job_id = uuid.uuid4().hex
    await asyncio.to_thread(_create_job, job_id, note["source_filename"])
    task = asyncio.create_task(
        service._run_job(
            job_id,
            None,
            note["source_filename"],
            style=request.style,
            language=request.language,
            instructions=request.instructions,
            replace_note_id=note_id,
            extracted_text=source["source_text"],
            content_hash=source["content_hash"],
        )
    )
    service._ACTIVE_JOBS[job_id] = task
    task.add_done_callback(lambda completed: service._ACTIVE_JOBS.pop(job_id, None))
    return {"job_id": job_id, "status_url": f"/api/documents/jobs/{job_id}"}


@router.patch("/notes/{note_id}")
async def update_document_note(note_id: int, update: NoteUpdate) -> dict:
    title = update.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Note title cannot be blank.")
    with _database() as connection:
        result = connection.execute(
            "UPDATE document_notes SET title = ?, updated_at = ? WHERE id = ?",
            (title, _timestamp(), note_id),
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


def _docx_bytes(note: dict) -> bytes:
    document = Document()
    document.add_heading(note["title"], level=0)
    document.add_paragraph(f"Source: {note['source_filename']}")
    document.add_paragraph("AI-generated, check against the source.")
    if note["style"] == "flashcards":
        cards = json.loads(note["summary"])["flashcards"]
        table = document.add_table(rows=1, cols=2)
        table.style = "Table Grid"
        table.rows[0].cells[0].text = "Question"
        table.rows[0].cells[1].text = "Answer"
        for card in cards:
            cells = table.add_row().cells
            cells[0].text = card["question"]
            cells[1].text = card["answer"]
    else:
        for line in note["summary"].splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            bullet = re.match(r"^[-*]\s+(.+)$", stripped)
            numbered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
            if heading:
                document.add_heading(heading.group(2), level=min(len(heading.group(1)), 4))
            elif bullet:
                document.add_paragraph(bullet.group(1), style="List Bullet")
            elif numbered:
                document.add_paragraph(numbered.group(1), style="List Number")
            else:
                document.add_paragraph(stripped)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


@router.get("/notes/{note_id}/export")
async def export_document_note(note_id: int, format: str = "markdown") -> Response:
    note = await asyncio.to_thread(_get_note, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="Document note not found.")
    if format not in {"markdown", "text", "docx", "json"}:
        raise HTTPException(status_code=422, detail="Export format must be markdown, text, docx, or json.")

    notice = "AI-generated, check against the source."
    if format == "markdown":
        content = f"# {note['title']}\n\nSource: {note['source_filename']}\n\n> {notice}\n\n{note['summary']}\n"
        media_type, extension = "text/markdown; charset=utf-8", "md"
    elif format == "text":
        content = f"{note['title']}\nSource: {note['source_filename']}\n{notice}\n\n{note['summary']}\n"
        media_type, extension = "text/plain; charset=utf-8", "txt"
    elif format == "json":
        if note["style"] != "flashcards":
            raise HTTPException(status_code=422, detail="JSON export is available for flashcard notes.")
        payload = {
            "title": note["title"],
            "source": note["source_filename"],
            "flashcards": json.loads(note["summary"])["flashcards"],
        }
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        media_type, extension = "application/json; charset=utf-8", "json"
    else:
        content = _docx_bytes(note)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        extension = "docx"
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "-", note["title"]).strip("-") or "rudra-note"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.{extension}"'},
    )


async def shutdown_document_jobs() -> None:
    await service.shutdown_document_jobs()
