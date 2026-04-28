"""Library reindex migration (P6 C45).

Spec phase6_library.md ## In line 79 字面: 「Library reindex migration
（跑過 P4/P5 既有 json 補 INSERT library_index row）」.

Use case: Library/Theorems/proved.lean accumulates re-export lines
across releases; the schema_v1 library_index table came online with
P6 C41. Pre-P6 promote_to_library writes (or hand-editor edits) may
leave proved.lean lines without a matching library_index row. This
tool reconciles the two.

Scope (C45 first cut):
  - Reads Library/Theorems/proved.lean lines that match the spike-024
    D-24-1 re-export schema:
        theorem <problem>.<slug> := Problems.<p>.Goals.<id>_<slug>.<slug>
  - For each line not already indexed (layer='Theorems' AND name=...),
    INSERT a library_index row with source_root_id resolved by
    cross-referencing goals (problem, slug). If multiple matching
    goals exist, the lowest-id is chosen (deterministic — earliest
    proved goal wins).
  - Skips malformed lines (caller surfaces them in `unparsed` list).

Out of scope:
  - Per-Problem `Problems/<p>/proved.lean` files (these never land in
    library_index — they are not framework-global).
  - Library/Counterexamples / Library/Constructions (deferred until
    Counterexample/ConstructionSearch ship — those layers don't
    accumulate pre-P6 entries today).

Public API:
    reindex_library(conn, base_dir) -> ReindexResult
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


# Regex for the canonical re-export line (spike-024 D-24-1):
#   theorem <problem>.<slug> := Problems.<problem>.Goals.<id>_<slug>.<slug>
# We tolerate trailing whitespace / newlines; we do NOT tolerate
# alternative formats (operator-edited proved.lean uses this format).
_RE_EXPORT = re.compile(
    r"^theorem\s+([\w]+)\.([\w]+)\s*:=\s*"
    r"Problems\.[\w]+\.Goals\.\d+_[\w]+\.[\w]+\s*$"
)


@dataclass
class ReindexResult:
    """Outcome of a single reindex_library run."""
    inserted: list[str] = field(default_factory=list)        # lib_name list
    already_indexed: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)      # lib_name w/o matching goal
    unparsed: list[str] = field(default_factory=list)        # raw line text
    library_file: str | None = None
    n_lines_scanned: int = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def reindex_library(
    conn: sqlite3.Connection,
    base_dir: str | Path,
) -> ReindexResult:
    """Walk Library/Theorems/proved.lean and reconcile with library_index.

    Returns a ReindexResult; rows whose names already index are listed
    under .already_indexed; new ones land in .inserted. Lines that
    don't parse as the canonical schema are surfaced in .unparsed (the
    operator decides whether they're hand-edits worth preserving).

    Conservative: this function never DELETEs index rows that lack a
    file line (those may be from other layers / deferred sources).
    """
    base = Path(base_dir)
    lib_path = base / "Library" / "Theorems" / "proved.lean"
    result = ReindexResult(library_file=str(lib_path))
    if not lib_path.exists():
        return result

    text = lib_path.read_text(encoding="utf-8")

    # Pre-load existing library_index names into a set to avoid one
    # SELECT per line.
    existing_names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM library_index WHERE layer = 'Theorems'"
        ).fetchall()
    }

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("--"):
            continue
        result.n_lines_scanned += 1
        m = _RE_EXPORT.match(line)
        if not m:
            result.unparsed.append(line)
            continue
        problem, slug = m.group(1), m.group(2)
        lib_name = f"{problem}.{slug}"
        if lib_name in existing_names:
            result.already_indexed.append(lib_name)
            continue
        # Resolve source_root_id by JOIN on goals (problem, slug).
        # Lowest id wins for determinism (earliest proved goal).
        goal_row = conn.execute(
            "SELECT id FROM goals "
            "WHERE problem = ? AND slug = ? AND status = 'proved' "
            "ORDER BY id ASC LIMIT 1",
            (problem, slug),
        ).fetchone()
        if goal_row is None:
            # File line references a goal we cannot find. Skip the
            # INSERT — operator inspects unresolved + decides whether
            # to backfill the goals row or remove the file line.
            result.unresolved.append(lib_name)
            continue
        source_id = goal_row[0]
        with conn:
            conn.execute(
                "INSERT INTO library_index "
                "(layer, name, path, source_root_id, committed_at) "
                "VALUES ('Theorems', ?, ?, ?, ?)",
                (lib_name, str(lib_path), source_id, _now()),
            )
        existing_names.add(lib_name)
        result.inserted.append(lib_name)
    return result
