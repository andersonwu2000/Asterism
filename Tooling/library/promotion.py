"""Library promotion (P6 C41 + R3 audit fixes).

Implements impl §3.1 + spike-024 D-24-1 source-path format. Two
orthogonal write paths:

  1. **Library/Theorems/proved.lean** — only `origin='root'` proved
     theorems with type='classical' AND trust_set ⊆ LIBRARY_WHITELIST
     (architecture_impl.md:287/322 + phase6_library.md:230 字面:
     `Library.whitelist` is the framework-global config, **NOT**
     Problem.axioms — they are completely independent. C41 R3 HIGH-1
     fix.)
  2. **Per-Problem `Problems/<n>/proved.lean`** — every origin's
     status='proved' goal in that Problem (root / backward / forward /
     generalizer / refuter_negation; **construction_witness deferred**
     per task.md ## 延後 cycles + spec line 47-48).

Re-export line format (spike-024 D-24-1):
    theorem <problem>.<slug> := Problems.<problem>.Goals.<id>_<slug>.<slug>

Numeric-prefix caveat (spike-024 D-24-1 #6 + C39 R3 + C41 R3 MED-4):
when goal id is bare-numeric, the `<id>_<slug>` directory segment
violates Lean 4's identifier-must-start-with-letter rule. Promotion
emits a `library_promotion_warning` cascade event for the offending
entry; downstream lake build verify rejects it; we revert. The fix
options (rename convention or namespace wrapper) live in spike-024
D-24-1 #6 — shipped at C45+ when LIBRARY_BUILD_FAULT lands.

Concurrent-write protection via `library_lock(conn)` (Tooling/locks.py;
spike-022 D-22-1).

lake_verify default (C41 R3 HIGH-2 fix):
  - Default `lake_verify=None` raises NotImplementedError when invoked
    in production-shaped contexts (any path that isn't an explicit
    test seam) so a noop verify is never silent.
  - Set env `LIBRARY_VERIFY_NOOP=1` for unit-test fixtures that don't
    have a real lake env.
  - Production scheduler hook (scheduler._update_goal_proved) sets
    LIBRARY_VERIFY_NOOP for C41 because the real lake build is C45+
    work; every promotion ALSO emits `library_verify_skipped` so
    operators see the noop window in the audit trail.

Revert path (C41 R3 MED-1 conscious deviation): impl §3.1 step 5
literally also calls for "Goal status revert to attempting + INSERT
dead_attempts". The C41 framework treats Library promotion as a
downstream artifact of the proved goal — flipping the goal back to
attempting after cascade twin-refute already fired would create
worse inconsistency. The framework chooses the proved row as
source-of-truth and emits `library_promotion_partial_revert` event
when the partial-revert path runs, so operators can clean up the
goal manually if needed. spec backfill (architecture_impl.md §3.1)
deferred — orchestrator note for user review.

Public API:
    LIBRARY_WHITELIST: frozenset[str]    -- Library.whitelist constant
    promote_to_library(conn, goal_id, base_dir, *,
                       lake_verify=None, emit_event=None) -> PromotionResult
    PromotionResult dataclass

Out of scope (C44+):
    - Cross-Problem axiom coverage check CLI binding (C44; C42 added
      Tooling/library/check_deps.py wrapper)
    - Library/Counterexamples / Constructions json indexing migration
      tool (C45)
    - Real lake build verifier + LIBRARY_BUILD_FAULT env hook (C45)
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from Tooling.locks import library_lock
from Tooling.subsystems.cache import invalidate_for_library_write


# Library/Theorems/proved.lean whitelist — framework-global per
# architecture_impl.md:287/322 + phase6_library.md:230 字面. P6 hardcodes
# the canonical 3-axiom set; P7 C55 will introduce a runtime config
# command (`asterism config get/set library.whitelist`), at which point
# this constant becomes a fallback default.
LIBRARY_WHITELIST: frozenset[str] = frozenset({
    "propext", "Quot.sound", "Classical.choice",
})


# Origins the per-Problem proved.lean re-exports.
# construction_witness deferred per task.md ## 延後 cycles.
_PER_PROBLEM_ORIGINS: frozenset[str] = frozenset({
    "root", "backward", "forward", "generalizer", "refuter_negation",
})

# Library/Theorems/proved.lean only re-exports user-injected roots.
_LIBRARY_THEOREMS_ORIGIN: str = "root"

# Match a fully-numeric goal id prefix in the source path's directory
# segment (e.g. "42_add_comm" → numeric prefix). C41 R3 MED-4 caveat.
_NUMERIC_PREFIX_RE = re.compile(r"^\d")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PromotionResult:
    """Outcome of one promote_to_library call."""
    goal_id: int
    library_theorems_appended: bool = False  # main library/proved.lean
    per_problem_appended: bool = False        # Problems/<p>/proved.lean
    library_index_inserted: bool = False
    skipped_reason: str | None = None         # if no path applied
    reverted: bool = False
    revert_reason: str | None = None
    lines_written: list[str] = field(default_factory=list)


def _re_export_line(goal: dict) -> str:
    """Format the re-export line per spike-024 D-24-1.

    Schema: theorem <problem>.<slug> := <fully-qualified-source-path>
    where source = Problems.<problem>.Goals.<id>_<slug>.<slug>.
    """
    p = goal["problem"]
    g_id = goal["id"]
    slug = goal["slug"]
    source = f"Problems.{p}.Goals.{g_id}_{slug}.{slug}"
    return f"theorem {p}.{slug} := {source}\n"


def _qualifies_for_library_theorems(
    goal: dict,
) -> tuple[bool, str | None]:
    """Check the architecture.md §6 + impl §5.3 acceptance gate for the
    main Library/Theorems/proved.lean. Returns (qualifies, skip_reason).

      - origin must be 'root'
      - status must be 'proved'
      - answer_data.type must be 'classical'
      - trust_set must ⊆ LIBRARY_WHITELIST (framework-global axiom set,
        NOT the Problem's META.md axioms — C41 R3 HIGH-1 fix per spec
        impl §5.3 line 322 字面)

    skip_reason is set when not qualifying so the caller can record
    why no append happened.
    """
    if goal.get("origin") != _LIBRARY_THEOREMS_ORIGIN:
        return False, f"origin={goal.get('origin')!r} not 'root'"
    if goal.get("status") != "proved":
        return False, f"status={goal.get('status')!r} not 'proved'"
    ad_raw = goal.get("answer_data")
    if not ad_raw:
        return False, "answer_data missing"
    try:
        ad = json.loads(ad_raw) if isinstance(ad_raw, str) else ad_raw
    except json.JSONDecodeError as exc:
        return False, f"answer_data malformed: {exc}"
    if ad.get("type") != "classical":
        return False, f"answer_data.type={ad.get('type')!r} not 'classical'"

    # trust_set whitelist check vs LIBRARY_WHITELIST.
    ts_raw = goal.get("trust_set")
    if ts_raw is None:
        return False, "trust_set missing — cannot verify whitelist"
    try:
        ts = json.loads(ts_raw) if isinstance(ts_raw, str) else ts_raw
    except json.JSONDecodeError as exc:
        return False, f"trust_set malformed: {exc}"
    used_axioms = []
    for entry in ts:
        if isinstance(entry, dict) and entry.get("kind") == "lean_axiom":
            n = entry.get("name")
            if n:
                used_axioms.append(n)
    rejected = [n for n in used_axioms if n not in LIBRARY_WHITELIST]
    if rejected:
        return False, (
            f"trust_set rejected by Library.whitelist: {rejected} "
            f"(allowed: {sorted(LIBRARY_WHITELIST)})"
        )
    return True, None


def _qualifies_for_per_problem(goal: dict) -> tuple[bool, str | None]:
    """Check the per-Problem `Problems/<p>/proved.lean` gate.

    Looser than the main library: any proved goal of an in-scope
    origin. construction_witness deferred per task.md ## 延後 cycles.
    """
    if goal.get("status") != "proved":
        return False, f"status={goal.get('status')!r} not 'proved'"
    origin = goal.get("origin")
    if origin not in _PER_PROBLEM_ORIGINS:
        return False, f"origin={origin!r} not in {sorted(_PER_PROBLEM_ORIGINS)}"
    return True, None


def _has_numeric_prefix(goal: dict) -> bool:
    """C41 R3 MED-4 / spike-024 D-24-1 #6: detect when the goal's id +
    slug combination would form an invalid Lean 4 identifier. Returns
    True if the directory segment `<id>_<slug>` starts with a digit
    (Lean 4 identifiers must start with a letter or underscore)."""
    g_id = goal.get("id")
    if g_id is None:
        return False
    return bool(_NUMERIC_PREFIX_RE.match(str(g_id)))


def _resolve_lake_verify(
    lake_verify: Callable[[Path], bool] | None,
) -> Callable[[Path], bool]:
    """C41 R3 HIGH-2 fix: refuse to noop silently.

    Resolution order (P6 C45: LIBRARY_BUILD_FAULT supersedes NOOP):
      1. `LIBRARY_BUILD_FAULT=1` env (P6 C45 test hook per
         docs/dev/test_hooks.md row 32) — return always-False so the
         caller hits the revert path. Takes precedence over an
         explicit lake_verify argument because the test purpose is to
         simulate a verifier rejection regardless of which verifier is
         in use.
      2. Explicit `lake_verify` argument (test fixture or production
         verifier) — used as-is.
      3. `LIBRARY_VERIFY_NOOP=1` env (set by scheduler hook in C41
         while the real verifier hasn't shipped) — return always-True
         WITH an audit-trail emit by the caller (handled separately).
      4. Otherwise raise NotImplementedError so a production caller
         that forgot to wire a verifier doesn't silently pass.
    """
    if os.environ.get("LIBRARY_BUILD_FAULT") == "1":
        return lambda _path: False
    if lake_verify is not None:
        return lake_verify
    if os.environ.get("LIBRARY_VERIFY_NOOP") == "1":
        return lambda _path: True
    raise NotImplementedError(
        "promote_to_library requires an explicit lake_verify callable; "
        "set LIBRARY_VERIFY_NOOP=1 for unit-test seams. Production "
        "verifier wiring lands in P6.C45 (LIBRARY_BUILD_FAULT env hook)."
    )


def _append_line(path: Path, line: str) -> None:
    """Append a single re-export line to the target file. Creates the
    file (with parent dirs) on first use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line)


def _truncate_appended_line(path: Path, line: str) -> None:
    """Best-effort revert: read file, drop last line if it equals `line`,
    write back. Caller has already verified `line` was appended in the
    same TX, so this is the matching truncate. If the line isn't the
    last, leaves file alone (lets operator inspect on next library
    audit)."""
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    if content.endswith(line):
        path.write_text(content[: -len(line)], encoding="utf-8")


def promote_to_library(
    conn: sqlite3.Connection,
    goal_id: int,
    base_dir: str | Path,
    *,
    lake_verify: Callable[[Path], bool] | None = None,
    emit_event: Callable[[str, dict], None] | None = None,
) -> PromotionResult:
    """Run Library promotion for a single goal.

    Args:
        conn: live sqlite3 connection
        goal_id: target goal
        base_dir: workspace root (Library/ + Problems/ live here)
        lake_verify: optional callable run after the file append. None
                     defaults via `_resolve_lake_verify` to either
                     LIBRARY_VERIFY_NOOP env path (unit tests) or
                     NotImplementedError (production safety per C41 R3
                     HIGH-2 fix).
        emit_event: optional cascade event emitter for audit trail.

    Returns:
        PromotionResult describing what was written / skipped /
        reverted.
    """
    result = PromotionResult(goal_id=goal_id)
    base = Path(base_dir)

    cur = conn.execute(
        "SELECT id, problem, slug, origin, status, answer_data, "
        "trust_set, lean_path "
        "FROM goals WHERE id = ?",
        (goal_id,),
    )
    row = cur.fetchone()
    if row is None:
        result.skipped_reason = f"goal {goal_id} not found"
        return result
    cols = [d[0] for d in cur.description]
    goal = dict(zip(cols, row))

    line = _re_export_line(goal)

    # Per-Problem proved.lean check — broader scope.
    pp_ok, pp_skip = _qualifies_for_per_problem(goal)
    # Library/Theorems/proved.lean check — Library.whitelist (framework
    # global, NOT Problem.axioms; C41 R3 HIGH-1 fix).
    lt_ok, lt_skip = _qualifies_for_library_theorems(goal)

    if not pp_ok and not lt_ok:
        result.skipped_reason = pp_skip or lt_skip or "no path qualified"
        return result

    # C41 R3 MED-4 numeric-prefix detection — flag for operator audit
    # but proceed; lake build verify is the strict gate that rejects
    # the entry per spike-024 D-24-1 #6.
    if (pp_ok or lt_ok) and _has_numeric_prefix(goal) and emit_event is not None:
        emit_event(
            "cascade",
            {
                "rule": "library_promotion_warning",
                "goal_id": goal_id,
                "reason": (
                    f"goal id={goal['id']} produces numeric-prefix "
                    f"module segment {goal['id']}_{goal['slug']!r}; "
                    "violates Lean 4 identifier rules — see "
                    "spike-024 D-24-1 #6"
                ),
            },
        )

    pp_path = base / "Problems" / goal["problem"] / "proved.lean"
    lt_path = base / "Library" / "Theorems" / "proved.lean"

    written_pp = False
    written_lt = False
    inserted_index = False
    skipped_lt_first_write_wins = False

    with library_lock(conn):
        try:
            if pp_ok:
                _append_line(pp_path, line)
                written_pp = True
                result.lines_written.append(f"{pp_path}:{line.rstrip()}")
            if lt_ok:
                # C41 R3 HIGH-3: SELECT existence BEFORE _append_line so
                # first-write-wins literally means no file append on
                # name collision (impl §3.1 step 3 字面).
                lib_name = f"{goal['problem']}.{goal['slug']}"
                cur = conn.execute(
                    "SELECT name FROM library_index "
                    "WHERE layer = 'Theorems' AND name = ?",
                    (lib_name,),
                )
                existing = cur.fetchone()
                if existing is None:
                    _append_line(lt_path, line)
                    written_lt = True
                    result.lines_written.append(f"{lt_path}:{line.rstrip()}")
                    conn.execute(
                        "INSERT INTO library_index "
                        "(layer, name, path, source_root_id, committed_at) "
                        "VALUES ('Theorems', ?, ?, ?, ?)",
                        (lib_name, str(lt_path), goal["id"], _now()),
                    )
                    inserted_index = True
                else:
                    skipped_lt_first_write_wins = True
                    if emit_event is not None:
                        emit_event(
                            "cascade",
                            {
                                "rule": "library_index_first_write_wins",
                                "name": lib_name,
                                "incumbent": existing[0],
                                "newcomer_goal_id": goal_id,
                            },
                        )
        except Exception as exc:
            if written_pp:
                _truncate_appended_line(pp_path, line)
            if written_lt:
                _truncate_appended_line(lt_path, line)
            result.reverted = True
            result.revert_reason = f"write/insert failure: {exc}"
            raise

    # SQL TX committed (library_lock exited normally).
    result.per_problem_appended = written_pp
    result.library_theorems_appended = written_lt
    result.library_index_inserted = inserted_index

    # Cache invalidation for library scope (impl §2.3 字面). Triggered
    # whenever a library file actually changed.
    if written_pp or written_lt:
        try:
            invalidate_for_library_write(conn)
        except Exception as exc:  # noqa: BLE001
            if emit_event is not None:
                emit_event(
                    "cascade",
                    {
                        "rule": "library_cache_invalidate_failed",
                        "goal_id": goal_id,
                        "error": str(exc),
                    },
                )

    # If we wrote nothing (skipped_lt_first_write_wins or pure pp-skip
    # path), no verify needed.
    if not (written_pp or written_lt):
        return result

    # C41 R3 HIGH-2 fix: explicit verifier resolution — None default
    # raises in production-shaped contexts.
    verifier = _resolve_lake_verify(lake_verify)
    if lake_verify is None and emit_event is not None:
        # LIBRARY_VERIFY_NOOP=1 path → record audit-trail event so the
        # noop window is observable until P6.C45 ships the real
        # verifier.
        emit_event(
            "cascade",
            {
                "rule": "library_verify_skipped",
                "goal_id": goal_id,
                "note": "LIBRARY_VERIFY_NOOP=1 (P6.C45+ wires real verifier)",
            },
        )

    try:
        verify_ok = verifier(lt_path if written_lt else pp_path)
    except Exception as exc:  # noqa: BLE001 — caller's verifier raised
        verify_ok = False
        result.revert_reason = f"lake_verify exception: {exc}"

    if not verify_ok:
        # Revert per impl §3.1 字面 (file truncate + library_index
        # DELETE). Goal status revert + dead_attempts INSERT are
        # documented as conscious deviation per C41 R3 MED-1 — the
        # framework treats Library promotion as a downstream artifact
        # and the proved goal stays the source-of-truth.
        if written_pp:
            _truncate_appended_line(pp_path, line)
            result.per_problem_appended = False
        if written_lt:
            _truncate_appended_line(lt_path, line)
            result.library_theorems_appended = False
        if inserted_index:
            with conn:
                conn.execute(
                    "DELETE FROM library_index "
                    "WHERE layer = 'Theorems' AND name = ?",
                    (f"{goal['problem']}.{goal['slug']}",),
                )
            result.library_index_inserted = False
        result.reverted = True
        if not result.revert_reason:
            result.revert_reason = "lake_verify returned False"
        if emit_event is not None:
            emit_event(
                "cascade",
                {
                    "rule": "library_promotion_partial_revert",
                    "goal_id": goal_id,
                    "reason": result.revert_reason,
                    "note": (
                        "spec impl §3.1 step 5 also calls for Goal status "
                        "revert + dead_attempts INSERT — C41 conscious "
                        "deviation, see promotion.py docstring"
                    ),
                },
            )

    return result
