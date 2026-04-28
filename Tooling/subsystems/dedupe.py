"""Dedupe subsystem (P3 C20).

Wraps `tools/dedupe.lean` subprocess + integrates with the search_cache table.

Public API:
    dedupe(candidate_path, entries, conn, mode='strict', timeout=30.0,
           lake_cwd=None) -> DedupeResult

DedupeResult.outcome ∈ {"hit", "novel", "timeout"}
DedupeResult.entry_id: int | None  (set iff outcome == "hit")
DedupeResult.from_cache: bool

Spec §7.1: dedupe.lean returns NOVEL on candidate elab failure (容錯不報錯);
the wrapper does not surface a separate `elab_failed` outcome — diagnostics
go to stderr in dedupe.lean and surface via subprocess stderr if the caller
wants them.

Cache key: sha256("dedupe|" + mode + "|" + candidate_text + "|" +
                  json.dumps(sorted entry ids))
Cache scope: "dedupe"
Cache TTL: 3600s default (overridable by caller)

Test hooks (mutually exclusive — see docs/dev/test_hooks.md):
    DEDUPE_MOCK=force_hit      → return outcome='hit', entry_id=first entry
    DEDUPE_MOCK=force_miss     → return outcome='novel'
    DEDUPE_MOCK=force_timeout  → return outcome='timeout'

Silent-failure red lines (continues C13–C18 discipline):
    - lake subprocess rc != 0 with no JSON output → raise RuntimeError (do
      NOT silently fall back to NOVEL); caller must observe the failure.
    - JSON parse failure → raise RuntimeError.
    - Unknown DEDUPE_MOCK value → raise ValueError (matches C18 R3 pattern).

Timeout vs subprocess error asymmetry: subprocess.TimeoutExpired returns
DedupeResult(outcome='timeout') so the caller can surface it as a documented
outcome and decide retry policy. Search.py (sibling module) raises on timeout
because it has no equivalent outcome enum value — the asymmetry is intentional
and documented in both modules' docstrings.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_DEDUPE_LEAN = Path(__file__).parents[2] / "tools" / "dedupe.lean"
# Spec §2.1: dedupe cache walks via mutation invalidation (C21 hook), not TTL.
# Use 1-year TTL as a soft floor — the real freshness guarantee comes from
# CommitWriter.finalize() killing dedupe rows on goals INSERT/UPDATE; TTL only
# bounds permanent residue if invalidation ever fails.
_DEFAULT_CACHE_TTL_SECS: float = 86400.0 * 365


@dataclass
class DedupeResult:
    outcome: str                     # "hit" | "novel" | "timeout"
    entry_id: int | None = None
    from_cache: bool = False


# ---------------------------------------------------------------------------
# Cache key + read/write
# ---------------------------------------------------------------------------


def _cache_key(candidate_text: str, entries: list[dict[str, Any]], mode: str) -> str:
    h = hashlib.sha256()
    h.update(b"dedupe|")
    h.update(mode.encode("utf-8"))
    h.update(b"|")
    h.update(candidate_text.encode("utf-8"))
    h.update(b"|")
    ids_sorted = sorted(int(e["id"]) for e in entries)
    h.update(json.dumps(ids_sorted).encode("utf-8"))
    return h.hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_cache(conn: sqlite3.Connection, query_hash: str) -> dict | None:
    row = conn.execute(
        "SELECT results, expires_at FROM search_cache WHERE query_hash = ?",
        (query_hash,),
    ).fetchone()
    if row is None:
        return None
    results_json, expires_at = row
    if expires_at < _now_iso():
        return None
    try:
        return json.loads(results_json)
    except json.JSONDecodeError:
        # Corrupt cache row — treat as miss; caller will overwrite on success.
        return None


def _write_cache(
    conn: sqlite3.Connection,
    query_hash: str,
    payload: dict,
    ttl_secs: float,
) -> None:
    """Write a dedupe row.  Both scope and mode columns are 'dedupe' so the
    C21 mutation invalidation hook (`WHERE mode='dedupe'` per spec §2.3)
    actually matches.  Without this, dedupe cache rows would never be
    invalidated by goals INSERT/UPDATE — a silent staleness bug at demo
    time."""
    expires = (
        datetime.now(timezone.utc) + timedelta(seconds=ttl_secs)
    ).isoformat()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO search_cache "
            "(query_hash, scope, mode, results, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (query_hash, "dedupe", "dedupe", json.dumps(payload), expires),
        )


# ---------------------------------------------------------------------------
# Subprocess invocation
# ---------------------------------------------------------------------------


def _parse_dedupe_json(stdout: str) -> dict | None:
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _run_lean_dedupe(
    candidate_path: Path,
    entries: list[dict[str, Any]],
    mode: str,
    lake_cwd: Path,
    timeout: float,
) -> DedupeResult:
    """Spawn lake env lean tools/dedupe.lean. Caller has already handled
    cache / mock; this function only does the subprocess + JSON parse."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8",
    ) as f:
        json.dump([{"id": int(e["id"]), "lean_path": str(e["lean_path"])}
                   for e in entries], f)
        entries_path = Path(f.name)

    try:
        cmd = [
            "lake", "env", "lean",
            "--run", str(_DEDUPE_LEAN),
            "--",
            "--candidate", str(candidate_path),
            "--against", str(entries_path),
            "--mode", mode,
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=str(lake_cwd),
                capture_output=True,
                text=True,

                encoding="utf-8", errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return DedupeResult(outcome="timeout")

        parsed = _parse_dedupe_json(result.stdout)
        if parsed is None:
            raise RuntimeError(
                f"dedupe.lean produced no JSON output (rc={result.returncode}); "
                f"stderr={result.stderr.strip()[:300]!r}"
            )

        kind = parsed.get("result", "")
        if kind == "hit":
            entry_id = parsed.get("entry_id")
            if not isinstance(entry_id, int):
                raise RuntimeError(
                    f"dedupe.lean 'hit' missing valid entry_id: {parsed!r}"
                )
            return DedupeResult(outcome="hit", entry_id=entry_id)
        if kind == "novel":
            return DedupeResult(outcome="novel")
        raise RuntimeError(f"dedupe.lean unknown result kind: {kind!r}")
    finally:
        entries_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Test mock hook
# ---------------------------------------------------------------------------


def _check_mock(entries: list[dict[str, Any]]) -> DedupeResult | None:
    mock = os.environ.get("DEDUPE_MOCK")
    if mock is None:
        return None
    if mock == "force_hit":
        if not entries:
            raise ValueError("DEDUPE_MOCK=force_hit but entries list is empty")
        return DedupeResult(outcome="hit", entry_id=int(entries[0]["id"]))
    if mock == "force_miss":
        return DedupeResult(outcome="novel")
    if mock == "force_timeout":
        return DedupeResult(outcome="timeout")
    raise ValueError(
        f"unknown DEDUPE_MOCK value: {mock!r}; "
        "valid: 'force_hit' | 'force_miss' | 'force_timeout'."
    )


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def dedupe(
    candidate_path: str | Path,
    entries: list[dict[str, Any]],
    conn: sqlite3.Connection | None = None,
    mode: str = "strict",
    timeout: float = 30.0,
    lake_cwd: str | Path | None = None,
    cache_ttl_secs: float = _DEFAULT_CACHE_TTL_SECS,
) -> DedupeResult:
    """Dedupe candidate against entries; return first matching entry id or NOVEL.

    Args:
      candidate_path: path to candidate .lean file (single user theorem).
      entries: [{"id": int, "lean_path": str}, ...]
      conn: sqlite3 connection (search_cache integration). None → no cache.
      mode: 'strict' | 'iff_lite' (iff_lite is C23 stub for P3 C20).
      timeout: subprocess wall-clock cap (default 30s per phase3 §Config).
      lake_cwd: working dir for lake subprocess. None → cwd of caller.
      cache_ttl_secs: cache row TTL (default 3600s).

    Caller passes already-elaborated entries; this function only loads candidate
    text for cache key (the .lean file is also read by Lean itself).
    """
    candidate_path = Path(candidate_path)

    # 1. Mock hook (test-only). Bypasses cache + subprocess.
    mock_result = _check_mock(entries)
    if mock_result is not None:
        return mock_result

    if mode not in ("strict", "iff_lite"):
        raise ValueError(
            f"unknown dedupe mode: {mode!r}; valid: 'strict' | 'iff_lite'."
        )

    # 2. Cache lookup.
    candidate_text = candidate_path.read_text(encoding="utf-8")
    cache_key = _cache_key(candidate_text, entries, mode)

    if conn is not None:
        cached = _read_cache(conn, cache_key)
        if cached is not None:
            return DedupeResult(
                outcome=cached["outcome"],
                entry_id=cached.get("entry_id"),
                from_cache=True,
            )

    # 3. Subprocess.
    if lake_cwd is None:
        lake_cwd = Path.cwd()
    result = _run_lean_dedupe(
        candidate_path, entries, mode, Path(lake_cwd), timeout,
    )

    # 4. Cache write (skip transient outcomes that may resolve next time).
    if conn is not None and result.outcome in ("hit", "novel"):
        _write_cache(conn, cache_key, {
            "outcome": result.outcome,
            "entry_id": result.entry_id,
        }, cache_ttl_secs)

    return result
