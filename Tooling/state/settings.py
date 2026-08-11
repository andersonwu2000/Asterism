"""Per-problem machine settings — the DB chokepoint (frontmatter
dissolve, 2026-07-07).

The four UI-owned Manifest settings (`axioms_whitelist`,
`forbidden_lemmas`, `library`) live in the
`problem_settings` table; Manifest.md keeps only the human prose
(Statement / Deliverables / Strategic notes). Every read and write
goes through this module.

Transition contract (dual-read window; hard cut only after every live
problem is migrated):

  * A key PRESENT in the DB wins. An ABSENT key falls back to the
    value parsed from Manifest.md (frontmatter, or the legacy
    `## Lemma hints` body section) — old problems keep working
    unmigrated.
  * `manifest.effective_axioms` is untouched: it reads the overlaid
    dataclass, and an EMPTY whitelist — from the DB or the file —
    still falls back to the framework defaults. Storing [] never
    weakens a gate.
  * Migration is lazy and write-side only: daemon startup (manifest
    load loop) and `init_problem` copy file values into the DB once;
    read-only surfaces (serve GET) never write.
  * Auditability: the yaml lines stop changing, so Ingest snapshots
    the EFFECTIVE settings into the regression manifest
    (state/regress.py) — whitelist history stays reconstructible from
    git.

A malformed DB row (bad JSON, wrong type) is DROPPED, not honored:
the reader falls back to the Manifest value for that key, so a
corrupt row can never hand a gate a weaker whitelist than the file
would have.
"""
from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

from .db import now

if TYPE_CHECKING:  # circular-import guard (manifest imports us lazily)
    from .manifest import Manifest

#: the settings this table owns: the UI trio (kept in LOCKSTEP with
#: manifest.UI_SETTING_KEYS — a drift-guard test pins the subset;
#: importing across would close the manifest→settings→db→manifest
#: cycle, so both stay literals) plus the machine-owned `signoff`
#: (benchmark adapters' unattended opt-out; never surfaced in the UI,
#: so deliberately NOT in UI_SETTING_KEYS).
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
    Absent keys mean "fall back to the Manifest"; a pre-settings DB
    (no table yet, e.g. an old file opened read-only) reads as empty.
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


def overlay(mfst: "Manifest", values: "dict[str, object]") -> None:
    """Stamp DB values onto the parsed dataclass IN PLACE — the one
    place dual-read happens. Consumers (effective_axioms, the gates,
    prompt assembly) keep reading plain dataclass fields."""
    for key, val in values.items():
        if key in SETTING_KEYS:
            setattr(mfst, key, val)


def frontmatter_drift(conn: sqlite3.Connection, problem: str,
                      mfst: "Manifest") -> "list[tuple[str, object, object]]":
    """`(key, file_value, db_value)` for every setting where the
    Manifest's frontmatter and the DB disagree.

    The two diverge silently by construction: creation writes the yaml
    block once, every later edit goes to the DB, and the UI shows the
    DB — so nobody is looking at the copy that went stale. Runtime is
    safe (the overlay makes the DB win at every gate), but the file
    then lies to whoever reads it next, which includes the operator and
    every tool that parses it without a connection.

    "A divergence nobody would notice" is exactly the shape that
    belongs in a check rather than in someone's memory, so this is
    what `asterism drift-check` calls (2026-08-11)."""
    db_values = read(conn, problem)
    out: "list[tuple[str, object, object]]" = []
    carried = getattr(mfst, "present_keys", None)
    for key in SETTING_KEYS:
        if key not in db_values:
            continue          # unmigrated: the file IS the value, no drift
        if carried is not None and key not in carried:
            # The file does not mention this key at all. Silence is not
            # disagreement — and treating it as such made the check a
            # one-way ratchet: creation writes `problem:` alone now, so
            # migrating an older Manifest to that shape means deleting
            # keys, and every deletion read as `[]` against the DB that
            # was seeded from it. That pushed the operator to keep the
            # stale copy this check exists to retire (2026-08-11).
            continue
        file_value = getattr(mfst, key, None)
        if not _valid(key, file_value):
            continue          # nothing parseable to disagree with
        db_value = db_values[key]
        if key in _LIST_KEYS:
            same = sorted(file_value) == sorted(db_value)
        else:
            same = file_value == db_value
        if not same:
            out.append((key, file_value, db_value))
    return out


def migrate_from_manifest(conn: sqlite3.Connection, problem: str,
                          mfst: "Manifest") -> int:
    """Copy the Manifest's values into the DB for every key that has
    no row yet (idempotent; a later UI edit is never clobbered by a
    stale file). Returns the number of keys written."""
    present = read(conn, problem)
    wrote = 0
    for key in SETTING_KEYS:
        if key in present:
            continue
        value = getattr(mfst, key, None)
        if not _valid(key, value):
            continue  # defensive: a garbled parse never lands in the DB
        write(conn, problem, key, value)
        wrote += 1
    return wrote
