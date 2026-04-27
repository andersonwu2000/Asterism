"""SQLite connection wrapper for Asterism."""
from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA = Path(__file__).with_name("schema_v1.sql")


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Return a WAL-mode SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Apply schema_v1.sql to *conn* (idempotent via CREATE TABLE IF NOT EXISTS)."""
    sql = _SCHEMA.read_text(encoding="utf-8")
    conn.executescript(sql)
