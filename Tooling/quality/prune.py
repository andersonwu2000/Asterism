"""End-of-run reconciliation + GC for OR parallelism artifacts.

OR parallelism produces two cleanup needs:

(1) **drift repair** (`reconcile_proved_goals`). When two sibling Verify
    workers race to rewrite a parent goal's lean_path, last-write-wins
    on the filesystem; the cascade-determined winner may not match the
    file-state winner. This function re-derives each proved goal's
    lean_path canonically from the DB winning strategy's scratch.

(2) **orphan GC** (`prune_problem`). Backwards that died and OR siblings
    that lost the race leave lean files in `proofs/`. Walking the DB
    winning chain identifies the live set; everything else is deletable.

Both run at dispatcher's all-roots-proved exit (self-healing invariant)
and via `asterism prune` CLI for partial state.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from ..state import db
from .dedupe import leading_decl_attrs


def _lean_path_to_module(workspace: Path, lean_path: Path) -> str:
    """workspace-relative path → Lean module name (mirrors pipeline.py)."""
    rel = lean_path.relative_to(workspace).with_suffix("")
    return ".".join(rel.parts)


_STRATEGY_IMPORT_PATTERN = "proofs._strategy_s"


def _extract_leading_annotation(current: str) -> str:
    """Preserve the `--` comment block at the top of `current` (before
    any `import` line) — that's the Strategist's proposal_md that
    `promote_to_alias` prepends as winner-strategy rationale for
    human readers + agent grep.

    Returns the block terminated by `\\n` (matching what
    `promote_to_alias` emits before the imports), or empty if no
    leading comments exist.
    """
    lines: list[str] = []
    for ln in current.splitlines():
        s = ln.strip()
        if s.startswith("import"):
            break
        if s == "" or s.startswith("--"):
            lines.append(ln)
            continue
        # Any other line type before the first import means this isn't
        # a canonical-shaped header — bail (defensive; promote_to_alias
        # only ever writes blanks + `--` comments before imports).
        return ""
    # Trim trailing blanks so the join below produces exactly the
    # `promote_to_alias` shape (annotation immediately followed by
    # imports, no extra blank line).
    while lines and lines[-1].strip() == "":
        lines.pop()
    if not lines:
        return ""
    return "\n".join(lines) + "\n"


def _canonical_alias_content(*, problem: str, goal_slug: str,
                             sid_token: str, scratch_module: str,
                             current: str) -> str:
    """Canonical end-of-run content for a proved goal's lean_path.

    Mirrors what Verify Step 2's `promote_to_alias` writes:
      <annotation>     ← `--` comment block from Strategist proposal_md
      <imports>        ← Mathlib/Defs + winner strategy module
      namespace ...
      def <slug> := @<problem>.<sid>
      end ...

    Reconcile-specific repair (vs Verify-time promote):
      - DROP `_strategy_s*` imports other than the winning strategy's,
        in case a sibling Verify race left a stale strategy import.
      - PRESERVE leading `--` comment block — without this, reconcile
        sees Verify's annotated output as 'drift' on every run, rewrites
        to strip the comments, invalidates olean for every proved goal,
        forces a full chain re-elaborate on the next integrity probe.
        Observed SG 2026-05-19: 13/13 strategy-proved goals all
        rewritten with annotation stripped → integrity probe blocked
        ~8min on a 180s budget → false "import failed".
    """
    annotation = _extract_leading_annotation(current)
    keep_imports: list[str] = []
    seen: set[str] = set()
    for ln in current.splitlines():
        s = ln.strip()
        if not s.startswith("import"):
            continue
        if _STRATEGY_IMPORT_PATTERN in s:
            continue  # drop ALL prior strategy imports (winner re-added below)
        if s in seen:
            continue
        seen.add(s)
        keep_imports.append(ln)
    winner = f"import {scratch_module}"
    if winner not in seen:
        keep_imports.append(winner)
    return (
        annotation
        + "\n".join(keep_imports) + "\n\n"
        f"namespace Problems.{problem}\n\n"
        f"{leading_decl_attrs(current, goal_slug)}"
        f"def {goal_slug} := @Problems.{problem}.{sid_token}\n\n"
        f"end Problems.{problem}\n"
    )


def reconcile_proved_goals(conn: sqlite3.Connection, workspace: Path,
                           problem: str) -> list[Path]:
    """Repair file/DB drift after OR Verify races.

    For each proved goal that has a 'succeeded' strategy, rewrite its
    lean_path to alias EXCLUSIVELY from that strategy's scratch — no
    stale imports from sibling strategies that finished concurrently.

    Form matches Verify Step 2's `_promote_to_alias` (a prior version
    emitted `theorem <slug> : <statement> := s<sid>`, which serializes
    only the goal's conclusion — binders from the original stub were
    stripped, breaking elaboration on any non-trivially-bound goal;
    that regenerated form would silently undo the def-alias fix every
    end-of-run reconcile). Idempotent — already-canonical files are
    left alone.

    Returns the list of repaired paths.
    """
    repaired: list[Path] = []

    rows = conn.execute(
        "SELECT g.id AS gid, g.slug, g.statement, g.lean_path,"
        "       s.id AS sid, s.scratch_path "
        "FROM goals g "
        "JOIN strategies s ON s.goal_id = g.id "
        "WHERE g.problem = ? AND g.status = 'proved'"
        "  AND s.status = 'succeeded'",
        (problem,),
    ).fetchall()

    for r in rows:
        if not r["scratch_path"]:
            continue
        scratch_abs = workspace / r["scratch_path"]
        if not scratch_abs.exists():
            continue
        parent_abs = workspace / r["lean_path"]
        scratch_module = _lean_path_to_module(workspace, scratch_abs)
        sid_token = f"s{int(r['sid'])}"
        try:
            current = parent_abs.read_text(encoding="utf-8") if parent_abs.exists() else ""
        except OSError:
            continue
        expected = _canonical_alias_content(
            problem=problem, goal_slug=r["slug"],
            sid_token=sid_token, scratch_module=scratch_module,
            current=current,
        )
        if current == expected:
            continue
        parent_abs.write_text(expected, encoding="utf-8")
        repaired.append(parent_abs)

    return repaired


def winning_chain(conn: sqlite3.Connection, problem: str) -> set[str]:
    """Set of repo-relative lean paths reachable from `problem`'s proved
    roots through 'succeeded' strategies. Includes both the goal lean files
    and the strategy scratch files of the winning chain."""
    keep: set[str] = set()
    visited: set[int] = set()

    def walk(goal_id: int) -> None:
        if goal_id in visited:
            return
        visited.add(goal_id)
        goal = conn.execute(
            "SELECT lean_path, alias_target_id FROM goals WHERE id = ?",
            (goal_id,),
        ).fetchone()
        if goal is None:
            return
        keep.add(goal["lean_path"])

        # Alias goals' lean files import their canonical's file.
        # Walk into the canonical so its lean_path stays in `keep` even
        # when the canonical is an orphan from a dead/superseded
        # strategy. Visited-set prevents loops; chain stays flat in
        # practice (insertion never aliases to an alias — see dedupe
        # _eligible_orphan_subgoals filter).
        if goal["alias_target_id"] is not None:
            walk(int(goal["alias_target_id"]))

        # A proved goal is closed either by Builder (no succeeded strategy)
        # or by a single 'succeeded' Strategy. Recurse only into the latter.
        s = conn.execute(
            "SELECT id, scratch_path FROM strategies"
            " WHERE goal_id = ? AND status = 'succeeded' LIMIT 1",
            (goal_id,),
        ).fetchone()
        if s is None:
            return
        if s["scratch_path"]:
            keep.add(s["scratch_path"])
        for sub in conn.execute(
            "SELECT subgoal_id FROM strategy_subgoals WHERE strategy_id = ?",
            (s["id"],),
        ):
            walk(int(sub["subgoal_id"]))

    for row in conn.execute(
        "SELECT id FROM goals"
        " WHERE problem = ? AND origin = 'root' AND status = 'proved'",
        (problem,),
    ):
        walk(int(row["id"]))

    return keep


# Match `import Problems.<problem>.proofs.<X>` where <problem> may
# itself be dotted (Domain.slug naming convention, e.g. Minif2f.aime_1997_p11
# or LinearAlgebra.jordan_normal_form). The historical pattern only
# allowed a single segment between Problems and proofs, silently failing
# to find any imports under the new convention. Combined with leaf-bypass
# strategies (strategy_subgoals=0 in DB; chain reachable only via .lean
# imports), this caused jordan_normal_form's prune (2026-05-25) to delete
# every cited proof file as orphan.
_IMPORT_RE = re.compile(
    r'^\s*import\s+(Problems(?:\.[\w_]+)+\.proofs\.[\w_]+)\s*$',
    re.MULTILINE,
)


def _expand_keep_via_imports(workspace: Path, problem: str,
                              keep_rel: set[str]) -> set[str]:
    """Transitively follow `import Problems.<problem>.proofs.<name>`
    lines starting from every .lean already in `keep_rel`, plus the
    problem's `Root.lean`. Returns the expanded keep set as repo-
    relative paths.

    Rationale (residue_thm 2026-05-21): the DB-only `winning_chain`
    walks `strategy_subgoals`, which captures Backward's decomposition
    edges but NOT Builder wrapper bodies that cite a proved sibling's
    short name (LESSONS line 1 anti-pattern that the framework's
    auto-import helper papers over). Without an import-aware expansion
    here, prune deletes the cited file as an "orphan" and the next
    cold lake build fails on `bad import` — even though the artifact
    is part of the winning chain at the .lean source level.

    Bounded by `Problems.<problem>.proofs.*` namespace so Mathlib /
    Defs / cross-problem imports never enlarge the keep set (those
    files aren't prune targets anyway).
    """
    # Module-name prefix (Lean: dot-separated) vs filesystem prefix
    # (path-separated): Domain.slug problems (LinearAlgebra.jordan_normal_form,
    # Minif2f.aime_1997_p11) require splitting dots into path segments at
    # the filesystem layer — `Problems/LinearAlgebra/jordan_normal_form/`,
    # not `Problems/LinearAlgebra.jordan_normal_form/`. `db.problem_dir`
    # owns this mapping; using f"Problems/{problem}/..." directly produced
    # a phantom path (Jordan 2026-05-25: every expand probe OSError'd on
    # the wrong path, frontier never grew, regex+expand both failed silently).
    proofs_prefix = f"Problems.{problem}.proofs."
    expanded = set(keep_rel)
    # Seed with Root.lean's imports too — Root sits outside proofs/
    # so it's never pruned, but its `import _strategy_s<root>` line
    # is the entry point to the chain.
    pdir_rel = db.problem_dir(workspace, problem).relative_to(workspace).as_posix()
    root_rel = f"{pdir_rel}/Root.lean"
    frontier = list(expanded) + [root_rel]
    proofs_dir_rel_prefix = f"{pdir_rel}/proofs/"
    visited: set[str] = set()
    while frontier:
        rel = frontier.pop()
        if rel in visited:
            continue
        visited.add(rel)
        abs_path = workspace / rel
        try:
            text = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in _IMPORT_RE.findall(text):
            if not m.startswith(proofs_prefix):
                continue
            mod_name = m.removeprefix(proofs_prefix)
            target_rel = f"{proofs_dir_rel_prefix}{mod_name}.lean"
            if target_rel in expanded:
                continue
            expanded.add(target_rel)
            frontier.append(target_rel)
    return expanded


def prune_problem(conn: sqlite3.Connection, workspace: Path,
                  problem: str, *, dry_run: bool = False,
                  force: bool = False) -> list[Path]:
    """Move every `.lean` in `Problems/<problem>/proofs/` that is not
    in the winning chain into a timestamped `.pruned/<ts>/` directory
    (NOT unlinked — reversible). Returns the list of moved paths.

    No-op (returns []) when the problem's root goal is not yet proved —
    we don't know what's safe to move during a running proof attempt.

    Idempotent: a second call after the first finds nothing to move.

    Safety net (2026-05-26, post-Jordan): operator can `mv .pruned/<ts>/* ./`
    back into proofs/ if a cold build breaks post-prune. The Jordan
    2026-05-25 wipe (~235 files, unrecoverable via prune) motivated this:
    even with all known prune logic bugs fixed (1660200) + dispatcher
    auto-prune removed (2026-05-26), defense-in-depth on the actual
    delete-step costs little and the recovery value is large. Operator
    cleans `.pruned/` manually after confirming the build still works.

    Also warns to stderr if any keep-set file is missing from disk —
    that's a sign of prior incomplete state (a past disaster's residue,
    or DB drift) and means the import-walk seeded from that missing file
    failed silently, potentially under-counting the keep set.
    """
    has_proved_root = conn.execute(
        "SELECT 1 FROM goals"
        " WHERE problem = ? AND origin = 'root' AND status = 'proved' LIMIT 1",
        (problem,),
    ).fetchone()
    if has_proved_root is None:
        return []

    # Integrity gate (2026-05-26, post-Jordan): refuse to prune unless
    # the root has passed `axiom_probe` (integrity_verified=1). Without
    # this guard, a mechanically-promoted "proved" root that actually
    # contains sorry in its transitive closure can trigger prune, which
    # then deletes "orphan" files that may include the very alternatives
    # needed to bisect the sorry chain (Jordan 2026-05-25). Operator
    # opts out via `force=True` (CLI: `asterism prune --force`) for
    # emergency situations where the integrity gate is known broken.
    if not force:
        ig = conn.execute(
            "SELECT integrity_verified FROM goals"
            " WHERE problem = ? AND origin = 'root' AND status = 'proved'"
            " ORDER BY id LIMIT 1",
            (problem,),
        ).fetchone()
        if ig is None or int(ig["integrity_verified"]) != 1:
            raise RuntimeError(
                f"prune refused for {problem!r}: root's "
                f"integrity_verified != 1 (axiom_probe has not passed). "
                f"Run the dispatcher to completion (which triggers "
                f"root_integrity_gate) or pass force=True to override."
            )

    keep_rel = winning_chain(conn, problem)
    # Expand keep set by following actual .lean import statements so
    # wrapper-cites-sibling pattern doesn't get its target file pruned.
    # See `_expand_keep_via_imports` docstring for incident reference.
    keep_rel = _expand_keep_via_imports(workspace, problem, keep_rel)
    keep_abs = {(workspace / rel).resolve() for rel in keep_rel}

    proofs_dir = db.problem_dir(workspace, problem) / "proofs"
    if not proofs_dir.exists():
        return []

    # Diagnostic: warn on keep-set files missing from disk. Walk skipped
    # those silently (read fails → continue), so their imports' files
    # may have been miscounted as orphan. Operator should investigate
    # before running with dry_run=False.
    import sys as _sys
    missing = [rel for rel in keep_rel if not (workspace / rel).exists()]
    if missing:
        print(f"[prune] WARNING: {len(missing)} keep-set files missing "
              f"from disk; their import edges were not walked. Sample:",
              file=_sys.stderr, flush=True)
        for rel in sorted(missing)[:5]:
            print(f"[prune]   - {rel}", file=_sys.stderr)
        if len(missing) > 5:
            print(f"[prune]   ... and {len(missing) - 5} more",
                  file=_sys.stderr)

    import shutil as _shutil
    from datetime import datetime as _dt
    pruned_dir: Path | None = None
    removed: list[Path] = []
    for f in proofs_dir.glob("*.lean"):
        if f.resolve() in keep_abs:
            continue
        if not dry_run:
            if pruned_dir is None:
                ts = _dt.now().strftime("%Y%m%d_%H%M%S")
                pruned_dir = proofs_dir.parent / ".pruned" / ts
                pruned_dir.mkdir(parents=True, exist_ok=True)
            try:
                _shutil.move(str(f), str(pruned_dir / f.name))
            except OSError:
                continue
        removed.append(f)
    if pruned_dir is not None and removed:
        print(f"[prune] {len(removed)} files moved to {pruned_dir} "
              f"(NOT unlinked). Restore: `mv {pruned_dir}/* {proofs_dir}/`. "
              f"Delete after build verification: `rm -rf {pruned_dir}`.",
              flush=True)
    return removed
