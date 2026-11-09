"""Local SQLite persistence for document jobs, notes, and summary cache."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from ..paths import data_dir


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
                    style TEXT NOT NULL DEFAULT 'brief',
                    language TEXT NOT NULL DEFAULT 'same',
                    instructions TEXT,
                    source_text TEXT,
                    content_hash TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS document_summary_cache (
                    cache_key TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            note_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(document_notes)")
            }
            migrations = {
                "style": "TEXT NOT NULL DEFAULT 'brief'",
                "language": "TEXT NOT NULL DEFAULT 'same'",
                "instructions": "TEXT",
                "source_text": "TEXT",
                "content_hash": "TEXT",
            }
            for name, declaration in migrations.items():
                if name not in note_columns:
                    connection.execute(f"ALTER TABLE document_notes ADD COLUMN {name} {declaration}")
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
            """INSERT INTO document_jobs
               (id, filename, status, progress, message, created_at, updated_at)
               VALUES (?, ?, 'queued', 0, ?, ?, ?)""",
            (job_id, filename, payload["message"], now, now),
        )
        connection.execute(
            """INSERT INTO document_job_events (job_id, event_type, payload, created_at)
               VALUES (?, 'progress', ?, ?)""",
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
    payload: dict = {"job_id": job_id, "status": status, "progress": progress, "message": message}
    if note_id is not None:
        payload["note_id"] = note_id
    if error:
        payload["error"] = error
    with _database() as connection:
        connection.execute(
            """UPDATE document_jobs
               SET status = ?, progress = ?, message = ?, summary = COALESCE(?, summary),
                   note_id = COALESCE(?, note_id), error = ?, updated_at = ?
               WHERE id = ?""",
            (status, progress, message, summary, note_id, error, now, job_id),
        )
        connection.execute(
            """INSERT INTO document_job_events (job_id, event_type, payload, created_at)
               VALUES (?, 'progress', ?, ?)""",
            (job_id, json.dumps(payload), now),
        )


def _get_job(job_id: str) -> Optional[dict]:
    with _database() as connection:
        row = connection.execute("SELECT * FROM document_jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def _get_events_after(job_id: str, event_id: int) -> list[dict]:
    with _database() as connection:
        rows = connection.execute(
            """SELECT id, event_type, payload FROM document_job_events
               WHERE job_id = ? AND id > ? ORDER BY id""",
            (job_id, event_id),
        ).fetchall()
    return [dict(row) for row in rows]


def _create_note(
    title: str,
    filename: str,
    summary: str,
    *,
    style: str = "brief",
    language: str = "same",
    instructions: Optional[str] = None,
    source_text: Optional[str] = None,
    content_hash: Optional[str] = None,
) -> int:
    now = _timestamp()
    with _database() as connection:
        cursor = connection.execute(
            """INSERT INTO document_notes
               (title, source_filename, summary, style, language, instructions,
                source_text, content_hash, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                title, filename, summary, style, language, instructions,
                source_text, content_hash, now, now,
            ),
        )
        return int(cursor.lastrowid)


def _list_notes() -> list[dict]:
    with _database() as connection:
        rows = connection.execute(
            """SELECT id, title, source_filename, summary, style, language,
                      instructions, created_at, updated_at
               FROM document_notes ORDER BY updated_at DESC, id DESC"""
        ).fetchall()
    return [dict(row) for row in rows]


def _get_note(note_id: int) -> Optional[dict]:
    with _database() as connection:
        row = connection.execute(
            """SELECT id, title, source_filename, summary, style, language,
                      instructions, created_at, updated_at
               FROM document_notes WHERE id = ?""",
            (note_id,),
        ).fetchone()
    return dict(row) if row else None


def _get_note_source(note_id: int) -> Optional[dict]:
    with _database() as connection:
        row = connection.execute(
            "SELECT source_text, content_hash FROM document_notes WHERE id = ?",
            (note_id,),
        ).fetchone()
    return dict(row) if row else None


def _cached_summary(cache_key: str) -> Optional[str]:
    with _database() as connection:
        row = connection.execute(
            "SELECT summary FROM document_summary_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()
    return row["summary"] if row else None


def _save_cached_summary(cache_key: str, summary: str) -> None:
    with _database() as connection:
        connection.execute(
            """INSERT OR REPLACE INTO document_summary_cache (cache_key, summary, created_at)
               VALUES (?, ?, ?)""",
            (cache_key, summary, _timestamp()),
        )


def _update_note_result(
    note_id: int,
    summary: str,
    style: str,
    language: str,
    instructions: Optional[str],
) -> None:
    with _database() as connection:
        connection.execute(
            """UPDATE document_notes
               SET summary = ?, style = ?, language = ?, instructions = ?, updated_at = ?
               WHERE id = ?""",
            (summary, style, language, instructions, _timestamp(), note_id),
        )
