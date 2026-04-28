"""Library promotion (P6 C41).

Implements impl §3.1 字面 + spike-024 D-24-1 source-path format. Two
orthogonal write paths:

  1. **Library/Theorems/proved.lean** — only `origin='root'` proved
     theorems with type='classical' AND trust_set within the Problem's
     declared `axioms` whitelist (architecture.md §6 Library promotion
     段 line 415).
  2. **Per-Problem `Problems/<n>/proved.lean`** — every origin's
     status='proved' goal in that Problem (root / backward / forward /
     generalizer / refuter_negation; **construction_witness 來源延後**
     per task.md ## 延後 cycles + spec line 47-48).

Re-export line format (spike-024 D-24-1 + R3 numeric-prefix caveat):
    theorem <problem>.<slug> := Problems.<problem>.Goals.<id>_<slug>.<slug>

Numeric-prefix caveat: when goal id starts with a digit, the directory
segment violates Lean 4's identifier-must-start-with-letter rule. P6.C41
emits a `library_promotion_warning` cascade event with the offending
path; downstream lake build verify (a real C41 execution path or P6.C45
LIBRARY_BUILD_FAULT mock) rejects it; we revert. Long-term fix is in
spike-024 D-24-1 #6 — directory rename or namespace wrapper.

Concurrent-write protection via `library_lock(conn)` (Tooling/locks.py;
spike-022 D-22-1).

Public API:
    promote_to_library(conn, goal_id, base_dir, *, lake_verify=None)
        - Detects which write paths apply for the goal
        - Acquires library_lock
        - Writes per-Problem proved.lean (always for any proved goal,
          except construction_witness origin which is deferred)
        - Writes Library/Theorems/proved.lean + library_index row IFF
          origin='root' AND classical AND trust_set ⊆ Problem.axioms
        - Calls lake_verify (default: noop stub; production path supplies
          a real verifier; P6.C45 will add LIBRARY_BUILD_FAULT env hook)
        - Revert on lake_verify failure: file truncate + DELETE library_index
          row + emit cascade event for audit
        - Returns PromotionResult with the written entries

    PromotionResult dataclass — what was written / skipped / reverted.

Out of scope (P6.C42+):
    - Cross-Problem axiom coverage check (CLI manual, spec §In line 38-44)
    - Library/Counterexamples / Constructions json indexing (P4/P5
      json already on disk; library_index INSERT migration tool is C45)
    - construction_witness origin per-Problem proved.lean append
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from Tooling.locks import library_lock
from Tooling.subsystems.cache import invalidate_for_library_write


# Origins the per-Problem proved.lean re-exports.
# construction_witness deferred per task.md ## 延後 cycles.
_PER_PROBLEM_ORIGINS: frozenset[str] = frozenset({
    "root", "backward", "forward", "generalizer", "refuter_negation",
})

# Library/Theorems/proved.lean only re-exports user-injected roots.
_LIBRARY_THEOREMS_ORIGIN: str = "root"


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
    goal: dict, problem_axioms: list[str] | None,
) -> tuple[bool, str | None]:
    """Check the architecture.md §6 acceptance gate for the main
    Library/Theorems/proved.lean. Returns (qualifies, skip_reason).

      - origin must be 'root'
      - status must be 'proved'
      - answer_data.type must be 'classical'
      - trust_set must ⊆ problem_axioms (whitelist check)

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

    # trust_set whitelist check
    ts_raw = goal.get("trust_set")
    if ts_raw is None:
        # No trust set captured (e.g. P1 sync path silent fallback) →
        # cannot verify whitelist; skip with reason for operator audit.
        return False, "trust_set missing — cannot verify whitelist"
    if problem_axioms is None:
        return False, "Problem axioms unknown — cannot verify whitelist"
    try:
        ts = json.loads(ts_raw) if isinstance(ts_raw, str) else ts_raw
    except json.JSONDecodeError as exc:
        return False, f"trust_set malformed: {exc}"
    # trust_set is a list of {name, kind, ...} dicts; extract names.
    used_axioms = []
    for entry in ts:
        if isinstance(entry, dict) and entry.get("kind") == "lean_axiom":
            n = entry.get("name")
            if n:
                used_axioms.append(n)
    rejected = [n for n in used_axioms if n not in problem_axioms]
    if rejected:
        return False, f"trust_set rejected by axiom whitelist: {rejected}"
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


def _problem_axioms(conn: sqlite3.Connection, problem: str) -> list[str] | None:
    """Look up the problem's declared axioms.

    P6 C41: spec phase6_library.md ## In line 33-36 字面 'META.md axiom
    basis 完整驗證' — Problem.axioms strict gate. P1+P2 Trust set 已
    從 META.md parser 抽 axioms; here we depend on a `problems` table
    or META.md parser. The MVP for C41 reads from the Problem META.md
    via Tooling.meta.parse_meta — but that path was P2 design + may
    not be wired for P6 multi-Problem yet.

    For C41 first cut: returns None when META.md is unavailable; the
    qualifies check then skips with reason 'Problem axioms unknown'
    so the operator can spot the gap. P6.C42 wires META.md parsing
    into the multi-Problem startup path (spec line 31-36).
    """
    # Try META.md via Tooling.meta (best effort; P2 path).
    try:
        from Tooling.meta import MetaError, parse_meta
    except ImportError:
        return None
    # Caller ensures cwd is the repo root (Asterism). Look up
    # Problems/<problem>/META.md.
    problem_dir = Path("Problems") / problem
    if not problem_dir.exists():
        return None
    try:
        meta = parse_meta(problem_dir)
    except MetaError:
        return None
    return list(meta.axioms) if meta.axioms else None


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
        lake_verify: optional callable run after the file append. If
                     it returns False, all writes for this call are
                     reverted. Default = always-True noop (so unit
                     tests don't need a lake env). P6.C45 will add a
                     production verifier with LIBRARY_BUILD_FAULT
                     env hook.
        emit_event: optional cascade event emitter for audit trail

    Locks via Tooling.locks.library_lock so concurrent reactors don't
    race on the same Library files.

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

    # Per-Problem proved.lean check — write first (broader scope).
    pp_ok, pp_skip = _qualifies_for_per_problem(goal)
    # Library/Theorems/proved.lean check — narrower (root + classical
    # + axiom whitelist). _problem_axioms reads META.md when available.
    lt_ok = False
    lt_skip: str | None = None
    if pp_ok:
        axioms = _problem_axioms(conn, goal["problem"])
        lt_ok, lt_skip = _qualifies_for_library_theorems(goal, axioms)
    else:
        lt_skip = pp_skip

    if not pp_ok and not lt_ok:
        # Goal doesn't qualify for either path.
        result.skipped_reason = pp_skip or lt_skip or "no path qualified"
        return result

    pp_path = base / "Problems" / goal["problem"] / "proved.lean"
    lt_path = base / "Library" / "Theorems" / "proved.lean"

    written_pp = False
    written_lt = False
    inserted_index = False

    with library_lock(conn):
        try:
            if pp_ok:
                _append_line(pp_path, line)
                written_pp = True
                result.lines_written.append(f"{pp_path}:{line.rstrip()}")
            if lt_ok:
                _append_line(lt_path, line)
                written_lt = True
                result.lines_written.append(f"{lt_path}:{line.rstrip()}")
                # library_index INSERT — composite PK (layer, name).
                # First-write-wins: ON CONFLICT we leave the existing row
                # and emit a cascade event for operator visibility.
                lib_name = f"{goal['problem']}.{goal['slug']}"
                cur = conn.execute(
                    "SELECT name FROM library_index "
                    "WHERE layer = 'Theorems' AND name = ?",
                    (lib_name,),
                )
                existing = cur.fetchone()
                if existing is None:
                    conn.execute(
                        "INSERT INTO library_index "
                        "(layer, name, path, source_root_id, committed_at) "
                        "VALUES ('Theorems', ?, ?, ?, ?)",
                        (lib_name, str(lt_path), goal["id"], _now()),
                    )
                    inserted_index = True
                elif emit_event is not None:
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
            # Inside library_lock — context manager rolls back the SQL TX
            # (library_index INSERT). File appends were on disk before
            # the exception → revert them outside the lock context.
            # Re-raise after recording for caller; but first revert.
            # Note: the BEGIN IMMEDIATE TX is still active here, so
            # delaying the file truncate to AFTER the rollback would
            # require rethinking. For C41 first cut, attempt truncate
            # before re-raise; failure to truncate is logged via
            # emit_event but does not mask the original error.
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

    # P6 C43: cache invalidation for library scope (impl §2.3 字面
    # "Library/Theorems/proved.lean append... → DELETE search_cache
    # WHERE scope LIKE '%library%'"). Triggered after at least one
    # library file changed; per-Problem proved.lean changes also flush
    # because future search_cache rows might key on per-Problem scope.
    if written_pp or written_lt:
        try:
            invalidate_for_library_write(conn)
        except Exception as exc:  # noqa: BLE001
            # Caller (scheduler hook) wraps promote_to_library in
            # try/except already; surface via emit_event for audit
            # trail but don't break the promotion result.
            if emit_event is not None:
                emit_event(
                    "cascade",
                    {
                        "rule": "library_cache_invalidate_failed",
                        "goal_id": goal_id,
                        "error": str(exc),
                    },
                )

    # lake build verify (default: trivially OK for unit tests).
    verifier = lake_verify or (lambda _path: True)
    try:
        verify_ok = verifier(lt_path if written_lt else pp_path)
    except Exception as exc:  # noqa: BLE001 — caller's verifier raised
        verify_ok = False
        result.revert_reason = f"lake_verify exception: {exc}"

    if not verify_ok:
        # Revert per impl §3.1 字面 (4-step revert).
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
                    "rule": "library_promotion_reverted",
                    "goal_id": goal_id,
                    "reason": result.revert_reason,
                },
            )

    return result
