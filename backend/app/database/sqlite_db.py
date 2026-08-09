"""
RUDRA AI - SQLite Database Module
Handles all structured data storage: conversations, settings, tasks, plugins, etc.
"""

import aiosqlite
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH: Path | None = None


def set_db_path(path: Path) -> None:
    """Set the database file path."""
    global DB_PATH
    DB_PATH = path


async def get_db() -> aiosqlite.Connection:
    """Get an async database connection."""
    if DB_PATH is None:
        raise RuntimeError("Database path not set. Call set_db_path() first.")
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_database() -> None:
    """Initialize the database schema. Creates all tables if they don't exist."""
    logger.info("Initializing SQLite database at %s", DB_PATH)
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL DEFAULT 'User',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT,
                category TEXT NOT NULL DEFAULT 'general',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'failed')),
                result TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS plugins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                version TEXT NOT NULL DEFAULT '1.0.0',
                description TEXT,
                path TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                installed_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                path TEXT NOT NULL,
                summary TEXT,
                content_hash TEXT,
                uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT,
                description TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT NOT NULL DEFAULT 'INFO',
                module TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Insert default user if not exists
            INSERT OR IGNORE INTO users (id, name) VALUES (1, 'User');

            -- Insert default settings
            INSERT OR IGNORE INTO settings (key, value, category) VALUES
                ('theme', 'dark', 'appearance'),
                ('model', 'qwen2.5:3b', 'ai'),
                ('temperature', '0.7', 'ai'),
                ('max_tokens', '2048', 'ai'),
                ('voice_enabled', 'true', 'voice'),
                ('tts_voice', 'en_US-lessac-medium', 'voice'),
                ('auto_save_memory', 'true', 'memory');
        """)
        await db.commit()
        logger.info("Database initialized successfully.")
    finally:
        await db.close()


# ─── Conversation CRUD ───────────────────────────────────────────────

async def create_conversation(title: str = "New Chat") -> int:
    """Create a new conversation and return its ID."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO conversations (title) VALUES (?)", (title,)
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_conversations(limit: int = 50, offset: int = 0) -> list[dict]:
    """Get all conversations, newest first."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT c.*, COUNT(m.id) as message_count 
               FROM conversations c 
               LEFT JOIN messages m ON c.id = m.conversation_id 
               GROUP BY c.id 
               ORDER BY c.updated_at DESC 
               LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def get_conversation_messages(conversation_id: int) -> list[dict]:
    """Get all messages in a conversation."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC",
            (conversation_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def add_message(
    conversation_id: int, role: str, content: str
) -> int:
    """Add a message to a conversation."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content),
        )
        # Update conversation timestamp
        await db.execute(
            "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
            (conversation_id,),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def update_conversation_title(conversation_id: int, title: str) -> None:
    """Update a conversation's title."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title, conversation_id),
        )
        await db.commit()
    finally:
        await db.close()


async def delete_conversation(conversation_id: int) -> None:
    """Delete a conversation and all its messages."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        await db.commit()
    finally:
        await db.close()


# ─── Settings CRUD ───────────────────────────────────────────────────

async def get_setting(key: str) -> str | None:
    """Get a setting value by key."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else None
    finally:
        await db.close()


async def get_all_settings() -> dict:
    """Get all settings as a dictionary."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT key, value, category FROM settings")
        rows = await cursor.fetchall()
        return {row["key"]: {"value": row["value"], "category": row["category"]} for row in rows}
    finally:
        await db.close()


async def update_setting(key: str, value: str, category: str = "general") -> None:
    """Update or create a setting."""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO settings (key, value, category, updated_at) 
               VALUES (?, ?, ?, datetime('now')) 
               ON CONFLICT(key) DO UPDATE SET value=?, updated_at=datetime('now')""",
            (key, value, category, value),
        )
        await db.commit()
    finally:
        await db.close()
