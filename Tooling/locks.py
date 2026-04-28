"""Cross-OS advisory locks (P6 C40).

Per spike-022 D-22-1: SQLite BEGIN EXCLUSIVE / IMMEDIATE wraps as
the portable file-locking primitive across Windows + POSIX. Avoids
fcntl (Windows-unsupported) and msvcrt.locking (region-level only,
awkward for whole-file append). Stdlib only — no third-party dep.

Use cases:
  - Library promotion (impl §3.1): protect concurrent appends to
    Library/Theorems/proved.lean from multiple reactor instances
  - schedulers liveness: scheduler.py's _register_scheduler /
    heartbeat update path uses bare SQL writes (atomic via SQLite
    isolation), but explicit advisory locks for whole-file
    Library/Counterexamples / Constructions json writes go through
    library_lock when those land in P6.C41/C43

Usage:

    from Tooling.locks import library_lock

    with library_lock(conn):
        # ... append to Library file + INSERT library_index row ...
        # release on context exit (commit or rollback)
"""
from __future__ import annotations

import contextlib
import sqlite3
from typing import Iterator


@contextlib.contextmanager
def library_lock(
    conn: sqlite3.Connection,
    *,
    mode: str = "IMMEDIATE",
) -> Iterator[None]:
    """Acquire a SQLite advisory lock for the Library write path.

    `mode` is the SQLite transaction mode — restricted to IMMEDIATE
    or EXCLUSIVE per spike-022 D-22-1 condition 1 (which only listed
    those two). Default IMMEDIATE — a reserved-write lock that blocks
    other writers but allows readers; sufficient for Library promotion
    (concurrent reactor instances are the only collision case in P6).

    DEFERRED is intentionally NOT supported (C40 R3 MED-2 fix):
    BEGIN DEFERRED does not acquire a write lock until the first
    write statement, so a second connection's BEGIN DEFERRED would
    not block — wrong semantics for an "advisory lock".

    On context exit:
      - normal exit  → COMMIT
      - exception     → ROLLBACK (re-raise)

    Raises sqlite3.OperationalError ("database is locked") if a
    second connection tries to acquire while this is held; caller
    typically retries with backoff.
    """
    if mode not in ("IMMEDIATE", "EXCLUSIVE"):
        raise ValueError(
            f"library_lock mode must be IMMEDIATE or EXCLUSIVE "
            f"(per spike-022 D-22-1); got {mode!r}"
        )
    conn.execute(f"BEGIN {mode}")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
