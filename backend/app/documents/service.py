"""Document extraction, summarization jobs, and the voice summary tool."""

import asyncio
import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Optional

from ..paths import data_dir, load_config
from ..tools.registry import get_tool_context, tool
from .chunk import chunk_text
from .extract import DocumentPasswordError, ScannedDocumentError, extract_document
from .prompts import NOTE_STYLES, build_prompt
from .storage import (
    _cached_summary,
    _create_job,
    _create_note,
    _get_job,
    _save_cached_summary,
    _update_job,
    _update_note_result,
)
from .summarize import summarize_text

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_EXTRACTED_CHARS = 500_000
CHUNK_SIZE_CHARS = 6_000
MAX_CHUNKS = 84
MAX_PDF_PAGES = 500
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".pptx"}
_ACTIVE_JOBS: dict[str, asyncio.Task] = {}
_SUMMARIZATION_SEMAPHORE = asyncio.Semaphore(1)


def _configured_limit(name: str, default: int) -> int:
    value = load_config().get(name, default)
    if not isinstance(value, int) or value <= 0:
        raise RuntimeError(f"Configuration value {name} must be a positive integer.")
    return value


def _max_upload_bytes() -> int:
    return _configured_limit("documents_max_upload_mb", 25) * 1024 * 1024


def _max_pdf_pages() -> int:
    return _configured_limit("documents_max_pages", MAX_PDF_PAGES)


def _extract_document(path: Path) -> str:
    return extract_document(
        path,
        max_chars=MAX_EXTRACTED_CHARS,
        max_pages=_max_pdf_pages(),
    )


def _chunk_text(text: str, max_chars: int = CHUNK_SIZE_CHARS) -> list[str]:
    return chunk_text(text, max_chars)


def _document_model() -> str:
    config = load_config()
    return config.get(
        "ollama_doc_model",
        config.get("ollama_voice_model", config.get("ollama_model", "qwen2.5:3b-instruct-q4_K_M")),
    )


async def _summarize_text(
    text: str,
    model: str,
    *,
    style: str = "brief",
    language: str = "same",
    instructions: Optional[str] = None,
    reduce: bool = False,
) -> str:
    return await summarize_text(
        text,
        model,
        style=style,
        language=language,
        instructions=instructions,
        reduce=reduce,
    )


async def _reduce_summaries(
    summaries: list[str],
    model: str,
    *,
    style: str,
    language: str,
    instructions: Optional[str],
) -> str:
    while len(summaries) > 1:
        summaries = [
            await _summarize_text(
                "\n\n".join(summaries[index : index + 6]),
                model,
                style=style,
                language=language,
                instructions=instructions,
                reduce=True,
            )
            for index in range(0, len(summaries), 6)
        ]
    return summaries[0]


def validate_note_options(style: str, language: str, instructions: Optional[str]) -> None:
    if style not in NOTE_STYLES:
        raise ValueError("Choose a supported note style.")
    if language not in {"same", "English", "Hindi", "Punjabi"}:
        raise ValueError("Choose a supported note language.")
    if style == "custom" and not (instructions and instructions.strip()):
        raise ValueError("Custom notes need an instruction.")
    build_prompt(style, language, instructions)


def _cache_key(
    content_hash: str,
    style: str,
    language: str,
    model: str,
    instructions: Optional[str] = None,
) -> str:
    identity = f"{content_hash}\0{style}\0{language}\0{model}\0{instructions or ''}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _validate_flashcards(summary: str) -> str:
    candidate = summary.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise RuntimeError("The document model did not return valid flashcard JSON.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("flashcards"), list):
        raise RuntimeError("The document model returned flashcards in an unsupported format.")
    if not all(
        isinstance(card, dict)
        and isinstance(card.get("question"), str)
        and isinstance(card.get("answer"), str)
        for card in payload["flashcards"]
    ):
        raise RuntimeError("The document model returned invalid flashcard entries.")
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def _process_text(
    job_id: str,
    filename: str,
    text: str,
    content_hash: str,
    *,
    style: str,
    language: str,
    instructions: Optional[str],
    replace_note_id: Optional[int] = None,
) -> None:
    model = _document_model()
    key = _cache_key(content_hash, style, language, model, instructions)
    summary = await asyncio.to_thread(_cached_summary, key)
    if summary is None:
        if _SUMMARIZATION_SEMAPHORE.locked():
            _update_job(job_id, "queued", 5, "Waiting for another document summarization.")
        async with _SUMMARIZATION_SEMAPHORE:
            chunks = _chunk_text(text)
            if len(chunks) > MAX_CHUNKS:
                raise ValueError(f"Document is too large to summarize in one job ({MAX_CHUNKS} sections maximum).")
            summaries: list[str] = []
            for index, chunk in enumerate(chunks):
                summaries.append(await _summarize_text(
                    chunk,
                    model,
                    style=style,
                    language=language,
                    instructions=instructions,
                ))
                progress = 10 + int(75 * (index + 1) / len(chunks))
                _update_job(
                    job_id,
                    "summarizing",
                    progress,
                    f"Summarized section {index + 1} of {len(chunks)}.",
                )
            if len(summaries) > 1:
                _update_job(job_id, "summarizing", 90, "Combining document sections.")
            summary = await _reduce_summaries(
                summaries,
                model,
                style=style,
                language=language,
                instructions=instructions,
            )
        if style == "flashcards":
            summary = _validate_flashcards(summary)
        await asyncio.to_thread(_save_cached_summary, key, summary)
    else:
        _update_job(job_id, "summarizing", 90, "Using the saved note for this document and style.")

    if replace_note_id is None:
        note_id = await asyncio.to_thread(
            _create_note,
            Path(filename).stem,
            filename,
            summary,
            style=style,
            language=language,
            instructions=instructions,
            source_text=text,
            content_hash=content_hash,
        )
    else:
        await asyncio.to_thread(
            _update_note_result,
            replace_note_id,
            summary,
            style,
            language,
            instructions,
        )
        note_id = replace_note_id
    _update_job(job_id, "completed", 100, "Note saved.", summary=summary, note_id=note_id)


async def _run_job(
    job_id: str,
    source_path: Optional[Path],
    filename: str,
    *,
    style: str = "brief",
    language: str = "same",
    instructions: Optional[str] = None,
    replace_note_id: Optional[int] = None,
    extracted_text: Optional[str] = None,
    content_hash: Optional[str] = None,
) -> None:
    try:
        if extracted_text is None:
            if source_path is None:
                raise RuntimeError("The document source is unavailable.")
            _update_job(job_id, "extracting", 5, "Extracting document text.")
            extraction = asyncio.create_task(asyncio.to_thread(_extract_document, source_path))
            try:
                text = await asyncio.shield(extraction)
            except asyncio.CancelledError:
                await asyncio.gather(extraction, return_exceptions=True)
                raise
        else:
            text = extracted_text
        if content_hash is None:
            if source_path is None:
                raise RuntimeError("The document fingerprint is unavailable.")
            content_hash = await asyncio.to_thread(
                lambda: hashlib.sha256(source_path.read_bytes()).hexdigest()
            )
        await _process_text(
            job_id,
            filename,
            text,
            content_hash,
            style=style,
            language=language,
            instructions=instructions,
            replace_note_id=replace_note_id,
        )
    except asyncio.CancelledError:
        _update_job(job_id, "cancelled", 0, "Document processing was cancelled.")
        raise
    except Exception as exc:
        _update_job(job_id, "failed", 0, "Document processing failed.", error=str(exc))
    finally:
        if source_path is not None:
            try:
                source_path.unlink(missing_ok=True)
            except OSError:
                print("[Documents] Could not remove a temporary document file.")


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
    from ..tools.files import resolve_file_reference

    source, error = resolve_file_reference(name)
    if error:
        return error
    if source is None:
        return "The selected document could not be found."
    if source.suffix.casefold() not in ALLOWED_EXTENSIONS:
        return f"Unsupported document type: {source.suffix or '(no extension)'}"
    try:
        if source.stat().st_size > _max_upload_bytes():
            limit_mb = _configured_limit("documents_max_upload_mb", 25)
            return f"The document exceeds the {limit_mb} MB processing limit."
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

    notify = get_tool_context().get("notify")

    async def run_voice_job() -> None:
        await _run_job(job_id, copy_path, source.name)
        job = await asyncio.to_thread(_get_job, job_id)
        if not notify or not job:
            return
        if job["status"] == "completed":
            await notify({"type": "notes_ready", "note_id": job["note_id"], "filename": source.name})
        else:
            await notify({"type": "document_error", "message": job.get("error") or job["message"]})

    task = asyncio.create_task(run_voice_job())
    _ACTIVE_JOBS[job_id] = task
    task.add_done_callback(lambda completed: _ACTIVE_JOBS.pop(job_id, None))
    return f"Summarizing {source.name}, I'll show it in the workspace."


async def shutdown_document_jobs() -> None:
    tasks = list(_ACTIVE_JOBS.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
