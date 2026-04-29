"""Search subsystem (P3 C20; P6.x patch 28 library DB).

Three scopes:
  - mathlib: subprocess to tools/search.lean (C20 stub returns []; full
             impl deferred per phase3_cache.md §Subsystem caveat).
  - library: SQL query on `goals` table for status='proved' rows in the
             same Problem (P6.x patch 28; replaces former search.lean stub
             that returned []). Each result is {"name": slug, "type":
             question, "score": 1.0}. Returns [] when problem_scope="".
  - local_goals: direct SQL on `goals` table (no Lean subprocess).

Public API:
    search(query, scope, kind, conn=None, lake_cwd=None,
           ttl_secs=None) -> SearchResult

SearchResult.results: list[dict]  (each: {"name": str, "type": str, "score": float}
                                   for mathlib/library; or
                                   {"id": int, "slug": str, "lean_path": str}
                                   for local_goals)
SearchResult.from_cache: bool

Cache TTL defaults (phase3 §Config + spike-010 D-10-1):
  mathlib     = 3600s
  library     = 3600s
  local_goals = 300s

Test hooks (mutually exclusive — see docs/dev/test_hooks.md):
    SEARCH_MOCK=record_calls  → bypass subprocess + SQL; record args; return [].
    SEARCH_MOCK=force_miss    → bypass subprocess; return [] (no SQL fallback).
    SEARCH_MOCK=force_hit     → bypass subprocess; return one synthetic entry.

Silent-failure red lines (continues C13–C18):
    - lake subprocess rc != 0 with no JSON → raise RuntimeError.
    - JSON parse fail → raise RuntimeError.
    - Unknown scope / kind / SEARCH_MOCK value → raise ValueError.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SEARCH_LEAN = Path(__file__).parents[2] / "tools" / "search.lean"

_TTL_DEFAULTS: dict[str, float] = {
    "mathlib":     3600.0,
    "library":     3600.0,
    "local_goals":  300.0,
}

_VALID_SCOPES = frozenset({"mathlib", "library", "local_goals"})
_VALID_KINDS = frozenset({"find_lemmas", "find_subgoals", "find_pattern", "find_mathlib"})


@dataclass
class SearchResult:
    results: list[dict] = field(default_factory=list)
    from_cache: bool = False


# In-memory log of search() calls when SEARCH_MOCK=record_calls is active;
# tests can read this to assert call sequence without monkey-patching.
_recorded_calls: list[dict] = []


def reset_recorded_calls() -> None:
    """Test helper: clear the SEARCH_MOCK=record_calls log."""
    _recorded_calls.clear()


def get_recorded_calls() -> list[dict]:
    """Test helper: snapshot of recorded call args."""
    return list(_recorded_calls)


# ---------------------------------------------------------------------------
# Cache key + read/write
# ---------------------------------------------------------------------------


def _cache_key(query: str, scope: str, kind: str, problem_scope: str = "") -> str:
    """Compose a cache key. ``problem_scope`` participates per spec §2.2 line 102:
    ``key = SHA256(scope_tuple + "|" + mode + "|" + query + "|" + problem_or_empty)``.

    Empty string for non-Problem-scoped queries (mathlib / library / inventory).
    Required for local_goals to prevent Problem A INSERT collisions wiping
    Problem B cached results once multi-Problem (P6) lands.

    Schema gap caveat: the search_cache table has no ``problem_scope`` column
    (P1 schema gap noted in C20 R2 audit MED-3); P3 includes problem_scope
    in the hash key only — there is no SQL filter by problem until P6 either
    amends the schema or accepts the hash-only collision-prevention.
    """
    h = hashlib.sha256()
    h.update(b"search|")
    h.update(scope.encode("utf-8"))
    h.update(b"|")
    h.update(kind.encode("utf-8"))
    h.update(b"|")
    h.update(query.encode("utf-8"))
    h.update(b"|")
    h.update(problem_scope.encode("utf-8"))
    return h.hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_cache(conn: sqlite3.Connection, query_hash: str) -> list[dict] | None:
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
        payload = json.loads(results_json)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        return None
    return payload


def _write_cache(
    conn: sqlite3.Connection,
    query_hash: str,
    scope: str,
    kind: str,
    results: list[dict],
    ttl_secs: float,
) -> None:
    expires = (
        datetime.now(timezone.utc) + timedelta(seconds=ttl_secs)
    ).isoformat()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO search_cache "
            "(query_hash, scope, mode, results, expires_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (query_hash, scope, kind, json.dumps(results), expires),
        )


# ---------------------------------------------------------------------------
# Subprocess invocation (mathlib / library scopes)
# ---------------------------------------------------------------------------


def _parse_search_json(stdout: str) -> dict | None:
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _run_lean_search(
    query: str,
    scope: str,
    kind: str,
    lake_cwd: Path,
    timeout: float,
) -> list[dict]:
    cmd = [
        "lake", "env", "lean",
        "--run", str(_SEARCH_LEAN),
        "--",
        "--query", query,
        "--scope", scope,
        "--kind", kind,
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
        # Timeout is observable; surface as empty results + raise so caller
        # can log. We don't silently swallow.
        raise RuntimeError(f"search.lean timed out (scope={scope}, query={query!r})")

    parsed = _parse_search_json(result.stdout)
    if parsed is None:
        raise RuntimeError(
            f"search.lean produced no JSON output (rc={result.returncode}, "
            f"scope={scope}); stderr={result.stderr.strip()[:300]!r}"
        )
    results = parsed.get("results", [])
    if not isinstance(results, list):
        raise RuntimeError(f"search.lean 'results' not a list: {parsed!r}")
    return results


# ---------------------------------------------------------------------------
# library scope (direct SQL — P6.x patch 28)
# ---------------------------------------------------------------------------


def _search_library(
    conn: sqlite3.Connection, problem_scope: str
) -> list[dict]:
    """Return proved sibling goals in the same Problem.

    `problem_scope` is the Problem name (goal['problem']). Empty string
    short-circuits to [] — cross-Problem library search is not supported
    here (Library/<p>/proved.lean is the cross-Problem promotion artifact;
    Backward agents only see siblings).

    `query` is intentionally ignored — Backward's Path B prompt benefits
    from seeing ALL proved siblings, not just slug-substring matches.
    Filtering down to 'relevant' siblings is the agent's job.
    """
    if not problem_scope:
        return []
    rows = conn.execute(
        "SELECT slug, question FROM goals "
        "WHERE problem = ? AND status = 'proved' AND commit_state = 'live' "
        "ORDER BY id ASC",
        (problem_scope,),
    ).fetchall()
    return [
        {"name": r[0], "type": r[1] or "", "score": 1.0}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# local_goals scope (direct SQL)
# ---------------------------------------------------------------------------


def _search_local_goals(conn: sqlite3.Connection, query: str) -> list[dict]:
    """Search committed Goals by slug (substring) or lean_path (substring).

    Demo-level matcher: returns goals whose slug or lean_path contains
    `query`. Real semantic match (statement_hash equality, type-pattern)
    is C23+ work once Backward integrates this.
    """
    rows = conn.execute(
        "SELECT id, slug, lean_path, statement_hash FROM goals "
        "WHERE commit_state = 'live' "
        "  AND (slug LIKE ? OR lean_path LIKE ?) "
        "ORDER BY id ASC",
        (f"%{query}%", f"%{query}%"),
    ).fetchall()
    return [
        {"id": r[0], "slug": r[1], "lean_path": r[2], "statement_hash": r[3]}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Test mock hook
# ---------------------------------------------------------------------------


def _check_mock(query: str, scope: str, kind: str) -> SearchResult | None:
    mock = os.environ.get("SEARCH_MOCK")
    if mock is None:
        return None
    if mock == "record_calls":
        _recorded_calls.append({"query": query, "scope": scope, "kind": kind})
        return SearchResult(results=[])
    if mock == "force_miss":
        return SearchResult(results=[])
    if mock == "force_hit":
        return SearchResult(results=[
            {"name": "_mock_hit", "type": "Prop", "score": 1.0},
        ])
    raise ValueError(
        f"unknown SEARCH_MOCK value: {mock!r}; "
        "valid: 'record_calls' | 'force_miss' | 'force_hit'."
    )


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def search(
    query: str,
    scope: str,
    kind: str,
    conn: sqlite3.Connection | None = None,
    lake_cwd: str | Path | None = None,
    ttl_secs: float | None = None,
    timeout: float = 30.0,
    problem_scope: str = "",
) -> SearchResult:
    """Search across mathlib / library (subprocess) or local_goals (SQL).

    Args:
      query: lookup text (interpretation depends on scope).
      scope: 'mathlib' | 'library' | 'local_goals'.
      kind:  'find_lemmas' | 'find_subgoals' | 'find_pattern' | 'find_mathlib'.
      conn:  sqlite3 connection. Required for local_goals + cache integration.
      lake_cwd: working dir for lake subprocess. None → cwd().
      ttl_secs: override default TTL for cache write.
      timeout: subprocess wall-clock cap.
      problem_scope: Problem name for local_goals scope; participates in cache
        key per spec §2.2 to prevent cross-Problem cache collisions. Empty
        string for non-Problem-scoped queries.
    """
    if scope not in _VALID_SCOPES:
        raise ValueError(
            f"unknown scope: {scope!r}; valid: {sorted(_VALID_SCOPES)}"
        )
    if kind not in _VALID_KINDS:
        raise ValueError(
            f"unknown kind: {kind!r}; valid: {sorted(_VALID_KINDS)}"
        )

    # 1. Mock hook (test-only). Bypasses cache + subprocess.
    mock_result = _check_mock(query, scope, kind)
    if mock_result is not None:
        return mock_result

    # 2. Cache lookup.
    cache_key = _cache_key(query, scope, kind, problem_scope)
    if conn is not None:
        cached = _read_cache(conn, cache_key)
        if cached is not None:
            return SearchResult(results=cached, from_cache=True)

    # 3. Real fetch.
    if scope == "local_goals":
        if conn is None:
            raise ValueError("local_goals scope requires conn")
        results = _search_local_goals(conn, query)
    elif scope == "library":
        # P6.x patch 28: library scope queries DB for proved siblings
        # in the same Problem instead of invoking the search.lean stub.
        if conn is None:
            raise ValueError("library scope requires conn")
        results = _search_library(conn, problem_scope)
    else:
        if lake_cwd is None:
            lake_cwd = Path.cwd()
        results = _run_lean_search(query, scope, kind, Path(lake_cwd), timeout)

    # 4. Cache write.
    if conn is not None:
        ttl = ttl_secs if ttl_secs is not None else _TTL_DEFAULTS[scope]
        _write_cache(conn, cache_key, scope, kind, results, ttl)

    return SearchResult(results=results, from_cache=False)
