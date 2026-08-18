"""Per-problem machine settings — the DB chokepoint (frontmatter
dissolve, 2026-07-07; sole source since the v40 Manifest retirement).

The four machine settings (`axioms_whitelist`, `forbidden_lemmas`,
`library`, `signoff`) live in the `problem_settings` table. Every read
and write goes through this module.

  * A key PRESENT in the DB is the value. An ABSENT key means the
    framework default (the dataclass field default on ProblemIntent).
  * `intent.effective_axioms` is untouched: it reads the overlaid
    dataclass, and an EMPTY whitelist still falls back to the
    framework defaults. Storing [] never weakens a gate.
  * Auditability: Ingest snapshots the EFFECTIVE settings into the
    regression manifest (state/regress.py).

A malformed DB row (bad JSON, wrong type) is DROPPED, not honored:
the reader keeps the framework default for that key, so a corrupt row
can never hand a gate a weaker whitelist than the default.
"""
from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

from .db import now

if TYPE_CHECKING:  # circular-import guard (intent imports us lazily)
    from .intent import ProblemIntent

#: the settings this table owns: the UI trio plus the machine-owned
#: `signoff` (benchmark adapters' unattended opt-out; never surfaced
#: in the UI).
SETTING_KEYS: tuple[str, ...] = (
    "axioms_whitelist", "forbidden_lemmas", "library", "signoff",
)

_LIST_KEYS = ("axioms_whitelist", "forbidden_lemmas")
_BOOL_KEYS = ("library", "signoff")


def _valid(key: str, value: object) -> bool:
    if key in _BOOL_KEYS:
        return isinstance(value, bool)
    return isinstance(value, list) and all(
        isinstance(x, str) for x in value)


def read(conn: sqlite3.Connection, problem: str) -> "dict[str, object]":
    """Settings rows for `problem` — ONLY the keys present and valid.
    Absent keys mean the framework default; a pre-settings DB (no table
    yet, e.g. an old file opened read-only) reads as empty.
    """
    try:
        rows = conn.execute(
            "SELECT key, value FROM problem_settings WHERE problem = ?",
            (problem,)).fetchall()
    except sqlite3.OperationalError:
        return {}
    out: dict[str, object] = {}
    for r in rows:
        key = str(r["key"])
        if key not in SETTING_KEYS:
            continue
        try:
            val = json.loads(r["value"])
        except (TypeError, ValueError):
            continue
        if _valid(key, val):
            out[key] = val
    return out


def write(conn: sqlite3.Connection, problem: str, key: str,
          value: object) -> None:
    """Upsert one setting. Raises ValueError on an unknown key or a
    type mismatch — a bad write must fail loudly, never store junk a
    reader would then silently drop."""
    if key not in SETTING_KEYS:
        raise ValueError(f"unknown setting key {key!r}")
    if not _valid(key, value):
        raise ValueError(
            f"setting {key!r} expects "
            f"{'bool' if key in _BOOL_KEYS else 'list[str]'},"
            f" got {type(value).__name__}")
    sql = ("INSERT INTO problem_settings (problem, key, value, updated_at)"
           " VALUES (?, ?, ?, ?)"
           " ON CONFLICT(problem, key) DO UPDATE SET"
           " value = excluded.value, updated_at = excluded.updated_at")
    params = (problem, key, json.dumps(value), now())
    try:
        conn.execute(sql, params)
    except sqlite3.OperationalError:
        # Pre-settings DB (the table ships via SCHEMA with no version
        # bump, so a DB last written before this feature lacks it) —
        # the write side may self-heal: init_schema is idempotent.
        from . import db as _db
        _db.init_schema(conn)
        conn.execute(sql, params)
    conn.commit()
    # Keep the durable seed (problem.json) in step — same chokepoint
    # discipline as the charter/word writers (v40).
    from . import intent as _intent
    ws = _intent._workspace_of(conn)
    if ws is not None:
        _intent.write_seed(conn, ws, problem)


def overlay(intent: "ProblemIntent", values: "dict[str, object]") -> None:
    """Stamp DB values onto the dataclass IN PLACE — the one place the
    settings read happens. Consumers (effective_axioms, the gates,
    prompt assembly) keep reading plain dataclass fields."""
    for key, val in values.items():
        if key in SETTING_KEYS:
            setattr(intent, key, val)
