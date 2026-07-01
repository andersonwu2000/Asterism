"""CLI: asterism init <p> | asterism run [--once] | asterism reset <p>
       | asterism status <p> [--json] | asterism prune [<p>] [--dry-run]
       | asterism library-verify [--no-build].

See architecture.md §9.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from ..state import brief, db, kb, kb_ingest, manifest, tree
from . import dispatcher
from ..quality import prune


# Daemon log lifecycle.
LOG_DIR = Path(".asterism") / "logs"
LOG_RETENTION_KEEP = 20  # most-recent N logs kept; older deleted on startup


class _Tee:
    """Write to multiple text streams. Used so the daemon's stdout
    appears on the operator's terminal AND in the per-run log file."""
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for st in self._streams:
            # Per-stream resilience: a write failure on one stream (e.g. a
            # legacy cp950 console choking on a char outside its range)
            # must not kill the daemon nor starve the other streams (the
            # UTF-8 log file is the canonical forensic artifact). Belt to
            # `_force_utf8_io`'s reconfigure suspenders.
            try:
                st.write(s)
                st.flush()
            except (UnicodeEncodeError, OSError, ValueError):
                pass
        return len(s)

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except (OSError, ValueError):
                pass

    def isatty(self):
        # Some downstream tools query isatty; report based on the
        # primary (terminal) stream.
        return getattr(self._streams[0], "isatty", lambda: False)()


def _log_filename(workspace: Path) -> str:
    """`<problem>_<model>_<UTC ts>.log` — `<problem>` falls back to
    `daemon` when the DB has no problems yet (e.g. first run before
    init), or `multi` when more than one problem is registered."""
    problem = "daemon"
    try:
        conn = db.connect()
        names = [r[0] for r in conn.execute(
            "SELECT name FROM problems ORDER BY name").fetchall()]
        conn.close()
        if len(names) == 1:
            problem = names[0]
        elif len(names) > 1:
            problem = "multi"
    except Exception:
        # DB missing / unreadable: keep 'daemon' default
        pass
    # Resolve via the same chain as the actual workers (per-pipeline
    # provider/model selection), not the legacy ASTERISM_AGENT_MODEL
    # env which lies when builder/backward use different models. Use
    # the builder's resolved model as the canonical label; combine
    # with backward's model when they differ so a mixed-model run is
    # visible from the filename.
    try:
        from ..llm import claude_cli as _cc
        b_model = _cc.resolve_model("builder")
        w_model = _cc.resolve_model("backward")
        model = b_model if b_model == w_model else f"{b_model}+{w_model}"
    except Exception:
        # Provider import failed (very early init / corrupt config):
        # fall back to legacy env so log filename always succeeds.
        model = os.environ.get("ASTERISM_AGENT_MODEL", "claude-sonnet-4-6")
    # Strip path-unsafe chars from model (just in case env carries them)
    model = re.sub(r"[^\w.+-]", "_", model)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{problem}_{model}_{ts}.log"


def _open_run_log(workspace: Path) -> Path:
    """Ensure `.asterism/logs/` exists, prune oldest beyond retention,
    and return the new log file's path. Caller is responsible for
    actually opening + redirecting."""
    log_dir = workspace / LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    _retain_recent_logs(log_dir, keep=LOG_RETENTION_KEEP)
    return log_dir / _log_filename(workspace)


def _retain_recent_logs(log_dir: Path, *, keep: int) -> list[Path]:
    """Delete .log files beyond the most-recent `keep` count
    (sorted by mtime). Returns the deleted paths for tests."""
    if not log_dir.exists():
        return []
    logs = sorted(log_dir.glob("*.log"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    deleted: list[Path] = []
    for old in logs[keep:]:
        try:
            old.unlink()
            deleted.append(old)
        except OSError:
            pass
    return deleted


# Root.lean lifecycle:
#  initial state — HAND-authored: `theorem main : <stmt> := by sorry`. An
#                  optional leading attribute is allowed: a Prop-class root
#                  may be `@[instance] theorem main : <PropClass> := by sorry`
#                  so the proved fact registers as a typeclass instance. The
#                  `theorem` keyword is load-bearing: Lean enforces
#                  `<stmt> : Prop`, so a Type-valued (data) `@[instance]` is
#                  rejected at the build gate — the framework only ever proves
#                  Props, never emits unverifiable data.
#  during run    — framework writes proofs/_strategy_sNN.lean files;
#                  Root.lean unchanged.
#  on root proved — `prune.reconcile_proved_goals` rewrites Root.lean to the
#                   def-alias form: `import Problems.X.proofs._strategy_sNN`
#                   then `def main := @Problems.X.sNN` (any leading
#                   `@[instance]` is preserved → `@[instance] def main := …`).
#  Manual editing of Root.lean is not expected.

# Lazy match between `theorem main` and the first `:=` so statements
# containing colons (`∀ p : ℕ, ...`) don't break the regex. A leading
# `@[instance]`/attribute sits before `theorem` and is outside the match,
# so extraction/classification handle attributed roots unchanged.
_SORRY_BODY_RE = re.compile(
    r"theorem\s+main\b.*?:=\s*by\s+sorry\b", re.DOTALL)
# Wrap form: bound to a strategy term `s\d+`. The promote-to-Root step
# always uses this exact shape.
_WRAP_BODY_RE = re.compile(
    r"theorem\s+main\b.*?:=\s*s\d+\b", re.DOTALL)

# Capture the `<stmt>` part of `theorem main : <stmt> := by sorry`.
# Used by `cmd_init` to pull goals.statement out of the hand-written
# Root.lean (the canonical source of truth — Manifest's `## Statement`
# section is no longer consumed by the framework).
_ROOT_STATEMENT_RE = re.compile(
    r"theorem\s+main\s*:\s*(.+?)\s*:=\s*by\s+sorry\b",
    re.DOTALL,
)


def _extract_root_statement(text: str) -> str | None:
    """Return the type-expression string from Root.lean's
    `theorem main : <stmt> := by sorry`, stripped of surrounding
    whitespace. Returns None if no matching declaration is present."""
    m = _ROOT_STATEMENT_RE.search(text)
    if m is None:
        return None
    return m.group(1).strip()


def _classify_root_body(text: str) -> str:
    """Classify Root.lean's `theorem main` body as one of:
    - 'sorry' : `:= by sorry`  (initial state, auto-created)
    - 'wrap'  : `:= s<N>`      (post-prove wrap form)
    - 'unknown': anything else (user-written sketch or in-progress)
    """
    if _SORRY_BODY_RE.search(text):
        return "sorry"
    if _WRAP_BODY_RE.search(text):
        return "wrap"
    return "unknown"


def _render_root_stub(
    problem: str, statement: str, pdir: Path, workspace: Path,
) -> str:
    """Render Root.lean sorry-stub content. Replays `open` clauses from
    Defs.lean via `manifest.inject_defs_opens` so Root.lean's theorem
    statement and any downstream proof can use Defs.lean's shorthand
    notation (e.g. `π` rather than `Real.pi`).
    """
    defs_import = (
        f"import Problems.{problem}.Defs\n"
        if (pdir / "Defs.lean").exists() else ""
    )
    stub = (
        f"import Mathlib\n{defs_import}\n"
        f"namespace Problems.{problem}\n\n"
        f"theorem main : {statement} := by sorry\n\n"
        f"end Problems.{problem}\n"
    )
    return manifest.inject_defs_opens(stub, problem=problem,
                                      workspace=workspace)


def cmd_init(args: argparse.Namespace) -> int:
    workspace = Path.cwd()
    problem = args.problem
    pdir = db.problem_dir(workspace, problem)
    mfst_path = pdir / "Manifest.md"
    if not mfst_path.exists():
        print(f"FAIL: {mfst_path} not found", file=sys.stderr)
        return 1

    mfst = manifest.parse(mfst_path)  # Statement section now optional

    # Require hand-written Defs.lean + Root.lean. The framework no longer
    # auto-generates Root.lean from the Manifest — the canonical statement
    # lives in the Lean signature so type errors / vocab bugs surface at
    # init time instead of after dispatching dozens of sub-goals against
    # a malformed spec (Polar 2026-05-23 lost ~50 goals to a typo'd
    # statement before agent RequestUserAmend caught it).
    defs_lean = pdir / "Defs.lean"
    root_lean = pdir / "Root.lean"
    if not defs_lean.exists():
        print(f"FAIL: {defs_lean} not found — author it manually",
              file=sys.stderr)
        return 1
    if not root_lean.exists():
        print(
            f"FAIL: {root_lean} not found. Author it manually with the\n"
            f"  canonical shape:\n"
            f"    import Mathlib\n"
            f"    import Problems.{problem}.Defs\n"
            f"    namespace Problems.{problem}\n"
            f"    theorem main : <your statement> := by sorry\n"
            f"    end Problems.{problem}",
            file=sys.stderr,
        )
        return 1

    # Dual type-check gate: both files must build cleanly before the
    # framework wires up the problem in the DB. --force bypasses the
    # gate for transitional situations only (e.g. operator knows the
    # error is in an unrelated downstream module).
    if not args.force:
        from ..pipeline._lake import lake_build
        for path in (defs_lean, root_lean):
            ok, msg = lake_build(workspace, path)
            if not ok:
                rel = path.relative_to(workspace).as_posix()
                print(
                    f"FAIL: {rel} did not type-check.\n{msg}",
                    file=sys.stderr,
                )
                return 1

    # Extract `goals.statement` from Root.lean's theorem signature.
    statement = _extract_root_statement(
        root_lean.read_text(encoding="utf-8"))
    if statement is None:
        print(
            f"FAIL: could not parse `theorem main : <stmt> := by sorry`\n"
            f"  from {root_lean.relative_to(workspace).as_posix()}.\n"
            f"  Use the canonical shape so init can extract the statement\n"
            f"  for the goals.statement DB column.",
            file=sys.stderr,
        )
        return 1

    # Statement-hygiene gate: the root statement must not hard-code its
    # own `Problems.<problem>.` namespace prefix. The theorem already
    # lives inside `namespace Problems.<problem>` (+ `import …Defs`), so
    # every self-namespace name resolves bare — writing the fully-
    # qualified form is a style slip, not a necessity. It matters
    # downstream: the Librarian re-derives this exact statement from a
    # Defs-free Library bridge (Gate B 秒殺). A bare `IsJordanForm`
    # re-resolves to the migrated `Library.…` version by swapping the
    # import/open; a hard-coded `Problems.<problem>.IsJordanForm` would
    # have to be string-rewritten — fragile, and the whole reason to
    # catch it at the source. (Cross-problem `Problems.<other>.` refs are
    # out of scope: 0 exist today, and a real one should be a Library
    # citation, not a raw Problems reference.)
    self_prefix = f"Problems.{problem}."
    if self_prefix in statement:
        print(
            f"FAIL: root statement hard-codes its own namespace "
            f"`{self_prefix}`.\n"
            f"  Drop the prefix and use the bare name — the theorem is "
            f"already inside\n"
            f"  `namespace Problems.{problem}` with `import "
            f"Problems.{problem}.Defs`,\n"
            f"  so e.g. `{self_prefix}Foo` should be written `Foo`.\n"
            f"  (Keeps the statement Library-portable for the Librarian's "
            f"re-derivation gate.)",
            file=sys.stderr,
        )
        return 1

    proofs_dir = pdir / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)

    conn = db.connect()
    db.init_schema(conn)

    existing = conn.execute(
        "SELECT 1 FROM problems WHERE name = ?", (problem,)
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
            (problem, str(mfst_path.relative_to(workspace).as_posix()), db.now()),
        )

    existing_goal = conn.execute(
        "SELECT id FROM goals WHERE problem = ? AND slug = 'main'",
        (problem,),
    ).fetchone()
    if existing_goal is None:
        rel_root = (pdir / "Root.lean").relative_to(workspace).as_posix()
        # Phase 5: root starts as `frozen`. Strategist's first_launch
        # trigger fires on frozen roots and may chain RequestUserAmend
        # (for missing statement-vocabulary in Defs.lean) / Inject(Forward)
        # (for missing prerequisite lemmas) before issuing Reopen(root) to
        # flip root frozen→open and release BFS. Replaces the earlier
        # `problems.bootstrap_done` gate; the column persists for
        # backwards-compat but is no longer read for dispatch decisions.
        gid = db.insert_goal(
            conn, problem=problem, slug="main",
            lean_path=rel_root, statement=statement,
            origin="root", depth=0, entry_kind="Backward",
            status="frozen",
        )
        print(f"OK: init {problem}, root goal id={gid}")
    else:
        print(f"OK: {problem} already initialized (goal id={existing_goal['id']})")
    conn.commit()
    # Initial TREE.md so readers see structure right after init.
    tree.write(conn, workspace, problem)
    # Initial BRIEF.md — framework-rendered cross-spawn stable context
    # (sandbox / forbidden lemmas / mathlib hints / library / strategic
    # notes). Refreshed at daemon startup if Manifest changes.
    brief.write(workspace, mfst)
    # No LESSONS.md seed: Phase 12 Model B made the KB the lessons SoT —
    # reflection writes `kb_entries`, Context reads `kb.query`; the old flat
    # LESSONS.md mirror (and its Edit-anchor seed) is retired.
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    workspace = Path.cwd()
    # Scope safety gate: a no-`--scope` run is workspace-wide — it
    # dispatches AND runs the recovery orphan-sweep across EVERY problem.
    # That is rarely intended and high-blast-radius (a stokes-scoped
    # restart once swept 148 committed proof files from other problems
    # before `--scope` was honored). The daemon is non-interactive, so the
    # guard refuses to start rather than prompt: require an explicit
    # `--all-problems` to confirm the rare workspace-wide intent.
    if getattr(args, "scope", None) is None and not getattr(
            args, "all_problems", False):
        print(
            "[cli] REFUSING to run without --scope: a no-scope run is "
            "WORKSPACE-WIDE (dispatch + orphan-sweep across every "
            "problem) and is rarely intended.\n"
            "      Re-run with --scope <problem> (e.g. "
            "--scope Geometry.stokes_theorem),\n"
            "      or pass --all-problems to confirm a deliberate "
            "workspace-wide run.",
            flush=True)
        return 2
    # Auto-tee daemon stdout/stderr into .asterism/logs/<...>.log so
    # post-run forensics + post-compact handoffs always have a canonical
    # artifact, while the operator still sees real-time output on the
    # terminal.
    log_path = _open_run_log(workspace)
    log_file = log_path.open("w", encoding="utf-8")
    print(f"[cli] log → {log_path.relative_to(workspace).as_posix()}",
          flush=True)
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    sys.stdout = _Tee(orig_stdout, log_file)
    sys.stderr = _Tee(orig_stderr, log_file)
    try:
        rc = dispatcher.run(
            workspace,
            once=getattr(args, "once", False),
            scope=getattr(args, "scope", None),
        )
        return rc
    except Exception:
        # Log the crash traceback HERE, while `sys.stderr` is still tee'd to
        # the log file and the file is still open. The `finally` below restores
        # `sys.stderr` and closes the log BEFORE an unhandled exception would
        # otherwise reach the interpreter's default handler — so without this
        # `except`, a `dispatcher.run` crash leaves `.asterism/logs/multi_*.log`
        # ending mid-tick with no traceback, making the daemon's self-
        # termination invisible (exactly what hid the green_theorem crash:
        # the log stopped cleanly at a `[dispatch] …` line). `print_exc`
        # writes to the tee'd `sys.stderr`, so the traceback lands in the log.
        print("[dispatcher] FATAL: unhandled exception — daemon exiting:",
              flush=True)
        traceback.print_exc()
        raise
    finally:
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr
        try:
            log_file.close()
        except OSError:
            pass


def cmd_init_batch(args: argparse.Namespace) -> int:
    """Bulk-init every Problem dir under <root> that has a Manifest.md.

    Walks `<root>` recursively to locate `Manifest.md` files. Each
    Manifest's parent directory is treated as a Problem directory; the
    problem slug is derived from its path relative to
    `<workspace>/Problems/` with `/` → `.`.

    Examples:
      Problems/sylvester_gallai/Manifest.md      → slug 'sylvester_gallai'
      Problems/Minif2f/algebra_1/Manifest.md     → slug 'Minif2f.algebra_1'

    `<root>` may be the workspace's `Problems/` itself (init everything
    not yet in DB) or any subtree (e.g. `Problems/Minif2f` to init only
    a benchmark batch).

    Idempotent: subdirs already in the DB stay put (cmd_init's own
    idempotency). Failures are reported per-problem; the batch keeps
    going so one broken Manifest doesn't block the rest.
    """
    workspace = Path.cwd()
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"FAIL: {root} is not a directory", file=sys.stderr)
        return 1
    problems_root = (workspace / "Problems").resolve()
    try:
        root.relative_to(problems_root)
    except ValueError:
        # Allow root == problems_root itself
        if root != problems_root:
            print(f"FAIL: {root} is not under {problems_root}",
                  file=sys.stderr)
            return 1

    manifests = sorted(root.rglob("Manifest.md"))
    if not manifests:
        print(f"OK: init-batch {root}: no Manifest.md found", flush=True)
        return 0

    initialized: list[str] = []
    failed: list[tuple[str, str]] = []
    for mpath in manifests:
        pdir = mpath.parent.resolve()
        try:
            slug = db.slug_from_problem_dir(workspace, pdir)
        except ValueError as e:
            failed.append((str(pdir), str(e)))
            continue
        ns = argparse.Namespace(problem=slug, force=False)
        try:
            rc = cmd_init(ns)
        except SystemExit as e:
            rc = int(e.code) if isinstance(e.code, int) else 1
        except Exception as e:
            failed.append((slug, str(e)))
            continue
        if rc == 0:
            initialized.append(slug)
        else:
            failed.append((slug, f"cmd_init returned {rc}"))

    print(f"\n[init-batch] {root} summary: "
          f"{len(initialized)} processed, {len(failed)} failed.",
          flush=True)
    if failed:
        for slug, why in failed:
            print(f"  - FAIL {slug}: {why}", file=sys.stderr)
        return 1
    return 0


def _soft_reset(problem: str) -> int:
    """Undo the cascade caused by spawn_fast_fail bursts (the
    spawn-fast-fail classifier sees provider-quota exhaustion as <10s
    rc=1 spam). The hard reset wipes everything; soft reset is surgical:

      1. Find dead_attempts on this problem with failure_reason in
         the spurious-failure set ('spawn_fast_fail').
      2. Delete those rows + matching pipelines rows.
      3. Recompute goals.attempts from surviving dead_attempts.
      4. Revive goals shelved purely from the cascade (no real
         Backward / Builder failure left).

    Doesn't touch proof files / Root.lean / Manifest. Operator runs
    after fixing the underlying provider issue (e.g. switching model
    after quota exhaust) to recover state without re-doing real work.
    """
    workspace = Path.cwd()
    pdir = db.problem_dir(workspace, problem)
    if not pdir.exists():
        print(f"FAIL: Problems/{problem}/ not found", file=sys.stderr)
        return 1
    conn = db.connect()
    db.init_schema(conn)
    SPURIOUS = ("spawn_fast_fail",)

    # Goals belonging to this problem
    gids = [r[0] for r in conn.execute(
        "SELECT id FROM goals WHERE problem = ?", (problem,)).fetchall()]
    if not gids:
        print(f"OK: soft-reset {problem} (no goals to clean)")
        return 0
    ph = ",".join("?" * len(gids))
    sph = ",".join("?" * len(SPURIOUS))
    spurious_pids = [r[0] for r in conn.execute(
        f"SELECT pipeline_id FROM dead_attempts "
        f"WHERE failure_reason IN ({sph}) "
        f"  AND ((target_kind='Goal' AND target_id IN ({ph})) "
        f"   OR  (target_kind='Strategy' AND target_id IN ("
        f"        SELECT id FROM strategies WHERE goal_id IN ({ph}))))",
        (*SPURIOUS, *gids, *gids)).fetchall()]
    if not spurious_pids:
        print(f"OK: soft-reset {problem} (no spurious dead_attempts found)")
        return 0
    pidph = ",".join("?" * len(spurious_pids))
    n_da = conn.execute(
        f"DELETE FROM dead_attempts WHERE pipeline_id IN ({pidph})",
        spurious_pids).rowcount
    n_pl = conn.execute(
        f"DELETE FROM pipelines WHERE id IN ({pidph})",
        spurious_pids).rowcount
    # Recompute goals.attempts = number of remaining (real) Goal-kind
    # dead_attempts on each goal in this problem.
    n_recomp = 0
    for gid in gids:
        n = conn.execute(
            "SELECT COUNT(*) FROM dead_attempts WHERE target_kind='Goal' "
            "AND target_id = ?", (gid,)).fetchone()[0]
        cur = conn.execute(
            "SELECT attempts, status FROM goals WHERE id = ?",
            (gid,)).fetchone()
        if cur is None:
            continue
        if cur["attempts"] != n:
            new_status = cur["status"]
            # If we're freeing a shelve cascaded from spurious failures,
            # revive the goal so the next dispatch can resume.
            from .dispatcher import SHELVE_THRESHOLD as _ST
            if cur["status"] == "shelved" and n < _ST:
                new_status = "open"
            conn.execute(
                "UPDATE goals SET attempts = ?, status = ?, updated_at = ?"
                " WHERE id = ?", (n, new_status, db.now(), gid))
            n_recomp += 1
    conn.commit()
    print(f"OK: soft-reset {problem}")
    print(f"  deleted {n_da} spurious dead_attempts + {n_pl} pipelines")
    print(f"  recomputed attempts on {n_recomp} goal(s)")
    return 0


def _robust_unlink(path: Path, retries: int = 5,
                   backoff_s: float = 0.5) -> bool:
    """Unlink with retry-on-OSError. Windows file locks (orphan
    lean/lake/claude holding handles after a kill) usually clear
    within 1-2s; we retry up to ~5×0.5s = 2.5s before giving up.
    Returns True on success, False on persistent failure."""
    import time
    for attempt in range(retries):
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError:
            if attempt + 1 < retries:
                time.sleep(backoff_s)
    # Final attempt — let the exception escape so caller sees it
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _robust_rmtree(path: Path, retries: int = 5,
                   backoff_s: float = 0.5) -> bool:
    """Like _robust_unlink but for directories. shutil.rmtree on
    Windows can hit transient locks too (especially if files inside
    are still being written by a dying process)."""
    import shutil
    import time
    for attempt in range(retries):
        try:
            shutil.rmtree(path, ignore_errors=False)
            return True
        except OSError:
            if attempt + 1 < retries:
                time.sleep(backoff_s)
    try:
        shutil.rmtree(path, ignore_errors=False)
        return True
    except OSError:
        return False


def cmd_reset(args: argparse.Namespace) -> int:
    """Wipe one Problem's DB rows + on-disk `proofs/` files. User-owned
    files (`Manifest.md`, `Defs.lean`, `Root.lean`) and anything outside
    `Problems/<p>/proofs/` are untouched — task #66 made Root.lean user-
    owned, so an operator who wants to re-init after reset must restore
    `theorem main : <stmt> := by sorry` manually. Idempotent — running
    on a clean Problem yields the same `OK` output without errors.

    Does NOT touch `.attempts/` (per-pipeline ephemeral state, possibly
    in-flight when other Problems are running). If the problem's daemon
    is dead, the operator can `rm -rf .attempts/` separately.

    `--soft`: skip the file/DB wipe; just clear spurious dead_attempts
    (spawn_fast_fail bursts) + revive cascade victims. Use after a
    quota-exhaust incident.

    Refuses to reset if no Manifest.md exists (signals user typo).
    """
    if getattr(args, "soft", False):
        return _soft_reset(args.problem)

    workspace = Path.cwd()
    problem = args.problem
    pdir = db.problem_dir(workspace, problem)
    if not pdir.exists():
        print(f"FAIL: Problems/{problem}/ not found", file=sys.stderr)
        return 1
    mfst_path = pdir / "Manifest.md"
    if not mfst_path.exists():
        print(f"FAIL: {mfst_path} not found", file=sys.stderr)
        return 1

    conn = db.connect()
    db.init_schema(conn)
    conn.execute("PRAGMA foreign_keys = ON")

    # Problem-keyed FK children, cleared FIRST (unconditional). Every table with
    # a `problem → problems(name)` FK blocks the `DELETE FROM problems` below if
    # it still has rows; `library_decls` also has a `source_goal_id → goals.id`
    # FK that blocks the goals DELETE. The FK children of `problems(name)` are:
    # goals + strategist_decisions (handled below by gid/problem) and these two:
    #   - `library_decls`: a (partially) library-ized problem's classified decls.
    #   - `kb_entries`: lessons/antipatterns (KB-as-SoT — the old flat LESSONS.md
    #     sweep's successor; reflection writes a row per global lesson).
    # Both observed 2026-06-28: derham_dd_zero reset crashed `FOREIGN KEY
    # constraint failed` at DELETE FROM problems — first on library_decls (2
    # classified), then on a kb_entries global lesson the run wrote.
    conn.execute("DELETE FROM library_decls WHERE problem = ?", (problem,))
    conn.execute("DELETE FROM kb_entries WHERE problem = ?", (problem,))

    gids = [r[0] for r in conn.execute(
        "SELECT id FROM goals WHERE problem = ?", (problem,)).fetchall()]
    sids: list[int] = []
    if gids:
        ph = ",".join("?" * len(gids))
        sids = [r[0] for r in conn.execute(
            f"SELECT id FROM strategies WHERE goal_id IN ({ph})",
            gids).fetchall()]

    # Delete in FK-safe order: leaf tables first.
    # dead_attempts.pipeline_id has an FK to pipelines, so dead_attempts
    # must be wiped before the matching pipelines rows.
    if sids:
        ph = ",".join("?" * len(sids))
        conn.execute(
            f"DELETE FROM strategy_subgoals WHERE strategy_id IN ({ph})",
            sids)
        conn.execute(
            f"DELETE FROM dead_attempts WHERE target_kind='Strategy' "
            f"AND target_id IN ({ph})", sids)
        conn.execute(
            f"DELETE FROM queue WHERE kind='Verify' AND target_id IN ({ph})",
            [str(s) for s in sids])
        conn.execute(f"DELETE FROM strategies WHERE id IN ({ph})", sids)
    if gids:
        ph = ",".join("?" * len(gids))
        conn.execute(
            f"DELETE FROM dead_attempts WHERE target_kind='Goal' "
            f"AND target_id IN ({ph})", gids)
        conn.execute(
            f"DELETE FROM queue WHERE kind!='Verify' AND target_id IN ({ph})",
            [str(g) for g in gids])
        # strategist_decisions.target_id → goals.id FK: any
        # ConfirmShelve / Reopen row with a non-NULL target_id pointing
        # at one of these goals blocks the goals DELETE. The full sd
        # cleanup happens below at the per-problem DELETE; here we
        # just clear the cross-row FK before the goals delete.
        # Observed SG 2026-05-17: 3 ConfirmShelve sd rows targeting
        # distinct_collinear / sg_contrapositive / main blocked reset
        # with `FOREIGN KEY constraint failed`.
        conn.execute(
            f"DELETE FROM strategist_decisions "
            f"WHERE target_id IN ({ph})", gids)
        conn.execute(f"DELETE FROM goals WHERE id IN ({ph})", gids)
    # Clean pipelines targeting this problem's now-deleted goals /
    # strategies. Without this, pipelines accumulates orphan rows
    # whose target_id no longer resolves — confuses forensics queries
    # and any future pipeline → strategy / goal joins.
    if gids:
        ph = ",".join("?" * len(gids))
        conn.execute(
            f"DELETE FROM pipelines WHERE target_kind='Goal' "
            f"AND target_id IN ({ph})", [str(g) for g in gids])
    if sids:
        ph = ",".join("?" * len(sids))
        conn.execute(
            f"DELETE FROM pipelines WHERE target_kind='Strategy' "
            f"AND target_id IN ({ph})", [str(s) for s in sids])
    # Phase 2 — Forward / Strategist pipelines targeting this problem.
    # Forward uses target_kind='Problem' + target_id=problem_name (see
    # migration_plan §C option 1); Strategist uses target_kind='Goal'
    # with target_id=problem.root.id (already covered by the goal-id
    # loop above). Clean the Problem-targeted rows here. Strategist
    # decision audit goes via FK on queue.decision_id (queue rows for
    # this problem already deleted above by target_id IN gids).
    #
    # dead_attempts.pipeline_id FK blocks pipelines DELETE if any
    # Forward dead_attempt rows still reference these pipelines —
    # observed SG run 2026-05-17 (cli reset crashed `FOREIGN KEY
    # constraint failed` because the earlier dead_attempts DELETE
    # passes only filtered by target_kind IN ('Strategy', 'Goal'),
    # missing the 'Problem' kind Forward writes).
    conn.execute(
        "DELETE FROM dead_attempts WHERE pipeline_id IN "
        "(SELECT id FROM pipelines WHERE target_kind='Problem' "
        " AND target_id = ?)",
        (problem,),
    )
    conn.execute(
        "DELETE FROM pipelines WHERE target_kind='Problem' AND target_id = ?",
        (problem,),
    )
    conn.execute(
        "DELETE FROM strategist_decisions WHERE problem = ?", (problem,),
    )
    conn.execute("DELETE FROM problems WHERE name = ?", (problem,))
    conn.commit()

    # Filesystem cleanup. Robust against Windows file locks (orphan
    # claude/lean process tree from a previously-killed daemon may
    # still hold handles for a few seconds). Two failure modes from the
    # original try/except OSError: pass:
    #   1. silent: user sees "0 proof file(s) removed" but stale L_*.lean
    #      / _strategy_*.lean stay → next dispatch sees inconsistent state
    #   2. ambiguous: same message regardless of whether deletion really
    #      happened or was blocked
    # Fix: retry with backoff (file locks usually clear in 1-2s after
    # holder dies), then RAISE on persistent failure so the operator
    # knows to kill the holder rather than silently inheriting stale
    # state. See docs/CLAUDE.md rule 9 (root-cause vs patch-around).
    proofs_dir = pdir / "proofs"
    deleted_files: list[str] = []
    failed_files: list[str] = []
    if proofs_dir.exists():
        # `*.backup` covers `L_<slug>.lean.backup` left behind by
        # Backward / Builder spawn-retry path (`shutil.copy2(goal_lean,
        # backup_path)`) when the pipeline got watchdog-killed before
        # `_restore_backup`. `*.verify_backup` / `*.verify_backup_s*`
        # cover Verify's atomic-write safety copy (sid-keyed so
        # concurrent sibling Verifies don't clobber each other); these
        # survived reset before — observed SG 2026-05-18, a stale
        # `.verify_backup_s9983` outlived reset, recovery's
        # sweep_lean_backups then copy2'd it back into a goal-less
        # `L_*.lean` orphan that Strategist `have`'d into a downstream
        # proof. `*.tmp` / `*.tmp_s*` are Verify's pre-replace staging
        # — also sid-keyed and never safe to keep across runs.
        for pattern in ("L_*.lean", "_strategy_*.lean", "*.backup",
                        "*.verify_backup", "*.verify_backup_s*",
                        "*.lean.tmp", "*.lean.tmp_s*"):
            for f in proofs_dir.glob(pattern):
                if _robust_unlink(f):
                    deleted_files.append(f.name)
                else:
                    failed_files.append(f.name)

    # Sweep gateway warmup artifacts. Current location is
    # `.asterism/runtime_slots/_gateway_slot_<i>.lean` (per-worker
    # didOpen surface). The workspace-root patterns + legacy
    # `_gateway_smoke_*.lean` / `_axiom_probe_*.lean` are retained for
    # migration cleanup of pre-move daemons / pre-current-design runs.
    runtime_slots = workspace / ".asterism" / "runtime_slots"
    if runtime_slots.exists():
        for f in runtime_slots.glob("_gateway_slot_*.lean"):
            if _robust_unlink(f):
                deleted_files.append(f"{runtime_slots.name}/{f.name}")
            else:
                failed_files.append(f.name)
    for pattern in ("_gateway_slot_*.lean", "_gateway_smoke_*.lean",
                     "_axiom_probe_*.lean"):
        for f in workspace.glob(pattern):
            if _robust_unlink(f):
                deleted_files.append(f.name)
            else:
                failed_files.append(f.name)

    # Drop per-problem artifacts that aren't in proofs/:
    #   - TREE.md: live tree rendering; goal rows gone → render
    #     would say "no root goal" anyway
    #   - LESSONS.md: legacy Model-A reflection cache. No longer created
    #     (Phase 12 Model B moved lessons into the KB); swept only to
    #     clean a pre-Model-B problem dir that still carries one
    #   - Root.lean.backup: spawn-side snapshot from in-pipeline retry
    #     path; only an unclean shutdown leaves it behind
    # BRIEF.md is intentionally NOT swept — it's auto-regenerated at
    # daemon startup from Manifest+Library.
    for name in ("TREE.md", "LESSONS.md", "Root.lean.backup"):
        p = pdir / name
        if p.exists():
            if _robust_unlink(p):
                deleted_files.append(name)
            else:
                failed_files.append(name)

    # Drop .drafts/ (postmortem progress notes from prior timed-out
    # spawns). Reset is meant to wipe state for a clean
    # baseline run; carrying over partial sketches would pre-bias a
    # clean reset.
    drafts_dir = pdir / ".drafts"
    if drafts_dir.exists():
        if not _robust_rmtree(drafts_dir):
            failed_files.append(".drafts/")

    if failed_files:
        print(f"FAIL: reset {problem}: could not remove "
              f"{len(failed_files)} file(s) after retries:",
              file=sys.stderr)
        for name in failed_files:
            print(f"  - {name}", file=sys.stderr)
        print("Cause is usually a stale claude/lean/lake process "
              "holding the file. Kill any running daemon and orphan "
              "lake/lean process tree, then retry.",
              file=sys.stderr)
        return 2

    # Root.lean is user-owned — `cmd_reset` no longer rewrites it. If
    # the file is in post-prove wrap form (`:= sNN`) the user must
    # restore the `:= by sorry` body before re-running `init`. (Old
    # behavior: auto-rewrite from Manifest.statement, which is no
    # longer the canonical source.)
    root_lean = pdir / "Root.lean"

    # Post-reset verification: scan the directories we cleaned and
    # raise loudly if anything we expected gone is still there. This
    # catches both "_robust_unlink reported success but file came
    # back" (race against a process still spawning) and any pattern
    # we forgot to sweep.
    leftovers: list[str] = []
    if proofs_dir.exists():
        for pattern in ("L_*.lean", "_strategy_*.lean", "*.backup",
                        "*.verify_backup", "*.verify_backup_s*",
                        "*.lean.tmp", "*.lean.tmp_s*"):
            for f in proofs_dir.glob(pattern):
                leftovers.append(f"proofs/{f.name}")
    for name in ("LESSONS.md", "Root.lean.backup", "TREE.md"):
        if (pdir / name).exists():
            leftovers.append(name)
    runtime_slots = workspace / ".asterism" / "runtime_slots"
    if runtime_slots.exists():
        for f in runtime_slots.glob("_gateway_slot_*.lean"):
            leftovers.append(f"{runtime_slots.name}/{f.name}")
    for pattern in ("_gateway_slot_*.lean", "_gateway_smoke_*.lean",
                     "_axiom_probe_*.lean"):
        for f in workspace.glob(pattern):
            leftovers.append(f.name)
    if leftovers:
        print(f"FAIL: reset {problem}: cleanup verified, but these "
              f"files reappeared / weren't matched:",
              file=sys.stderr)
        for name in leftovers:
            print(f"  - {name}", file=sys.stderr)
        return 2

    print(f"OK: reset {problem}")
    print(f"  DB rows: {len(gids)} goals, {len(sids)} strategies cleared")
    print(f"  Files: {len(deleted_files)} file(s) removed from proofs/; "
          f"Root.lean preserved (rewrite to sorry-stub manually before re-init)")
    attempts_dir = workspace / ".attempts"
    if attempts_dir.exists():
        att_n = sum(1 for _ in attempts_dir.iterdir())
        if att_n:
            print(f"  Note: .attempts/ has {att_n} dir(s) — untouched. "
                  f"Kill any running daemon then `rm -rf .attempts/` for "
                  f"full cleanup.")
    return 0


def _status_payload(conn, problem: str) -> dict:
    """Pure data: collect status info for one problem. Shared between
    text and --json output paths so both see the same shape."""
    goals = [dict(r) for r in conn.execute(
        "SELECT id, slug, status, attempts, depth FROM goals "
        "WHERE problem = ? ORDER BY id", (problem,)).fetchall()]
    if not goals:
        return {"problem": problem, "exists": False}

    gids = [g["id"] for g in goals]
    ph_g = ",".join("?" * len(gids))
    strategies = [dict(r) for r in conn.execute(
        f"SELECT id, goal_id, status FROM strategies "
        f"WHERE goal_id IN ({ph_g}) ORDER BY id", gids).fetchall()]
    sids = [s["id"] for s in strategies]

    # Recent dead_attempts targeting this problem's goals or strategies.
    deads = []
    if gids and sids:
        ph_s = ",".join("?" * len(sids))
        deads = [dict(r) for r in conn.execute(
            f"SELECT id, target_kind, target_id, failure_reason, ts "
            f"FROM dead_attempts "
            f"WHERE (target_kind='Goal' AND target_id IN ({ph_g})) "
            f"   OR (target_kind='Strategy' AND target_id IN ({ph_s})) "
            f"ORDER BY id DESC LIMIT 50",
            list(gids) + list(sids)).fetchall()]
    elif gids:
        deads = [dict(r) for r in conn.execute(
            f"SELECT id, target_kind, target_id, failure_reason, ts "
            f"FROM dead_attempts "
            f"WHERE target_kind='Goal' AND target_id IN ({ph_g}) "
            f"ORDER BY id DESC LIMIT 50", gids).fetchall()]

    fr_counts: dict[str, int] = {}
    for d in deads:
        fr_counts[d["failure_reason"]] = fr_counts.get(
            d["failure_reason"], 0) + 1

    # Recent pipelines (filtered to this problem). pipelines.target_id is TEXT,
    # so compare against str() of our int ids.
    gid_strs = {str(g) for g in gids}
    sid_strs = {str(s) for s in sids}
    pipes_recent = [dict(r) for r in conn.execute(
        "SELECT id, kind, target_id, target_kind, status, outcome, "
        "started_at, finished_at FROM pipelines "
        "ORDER BY finished_at DESC LIMIT 50").fetchall()]
    pipes_recent = [
        p for p in pipes_recent
        if (p["target_kind"] == "Goal" and p["target_id"] in gid_strs)
        or (p["target_kind"] == "Strategy" and p["target_id"] in sid_strs)
    ][:10]

    queue_count = conn.execute(
        f"SELECT count(*) FROM queue "
        f"WHERE (kind!='Verify' AND target_id IN ({ph_g}))"
        + (f" OR (kind='Verify' AND target_id IN ({','.join('?'*len(sids))}))"
           if sids else ""),
        list(map(str, gids)) + list(map(str, sids)),
    ).fetchone()[0] if gids else 0

    return {
        "problem": problem,
        "exists": True,
        "goals": goals,
        "strategies": strategies,
        "live_strategies_count": sum(
            1 for s in strategies if s["status"] == "proposed"),
        "queue_count": queue_count,
        "recent_failure_reasons": fr_counts,
        "recent_pipelines": pipes_recent,
        "dead_attempts_window": len(deads),
    }


def cmd_status(args: argparse.Namespace) -> int:
    """Show one Problem's current state: goal table, live strategies,
    queue depth, recent dead_attempts grouped by failure_reason, recent
    pipelines. Replaces the ad-hoc `python -c 'import sqlite3; ...'`
    one-liners. `--json` emits the same data structure for piping."""
    conn = db.connect()
    db.init_schema(conn)
    payload = _status_payload(conn, args.problem)

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
        return 0 if payload.get("exists") else 1

    if not payload.get("exists"):
        print(f"problem '{args.problem}' not initialized "
              f"(run `asterism init {args.problem}`)")
        return 1

    print(f"=== {payload['problem']} ===")
    print(f"\nGoals ({len(payload['goals'])}):")
    for g in payload["goals"]:
        print(f"  [{g['id']:>3}] depth={g['depth']} {g['status']:<11}"
              f" attempts={g['attempts']} {g['slug']}")
    print(f"\nLive strategies: {payload['live_strategies_count']} "
          f"of {len(payload['strategies'])} total")
    for s in payload["strategies"]:
        if s["status"] == "proposed":
            print(f"  [{s['id']:>3}] goal={s['goal_id']} {s['status']}")
    print(f"\nQueue depth: {payload['queue_count']}")

    fr = payload["recent_failure_reasons"]
    if fr:
        print(f"\nFailure reasons (last {payload['dead_attempts_window']} "
              f"dead_attempts):")
        for reason, count in sorted(fr.items(), key=lambda x: -x[1]):
            print(f"  {count:>3}  {reason}")

    pipes = payload["recent_pipelines"]
    if pipes:
        print(f"\nRecent pipelines (last {len(pipes)}):")
        for p in pipes:
            print(f"  {p['kind']:<8} {p['target_kind']}={p['target_id']:<3}"
                  f" {p['status']:<10} {p['outcome']}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Pre-flight diagnostic. Checks the toolchain (claude / gemini /
    lake), the Asterism.yaml config, every initialized Problem's
    Manifest, and on-disk state (`.attempts/` zombies + log retention).
    Output is icon-prefixed lines (`OK / FAIL / WARN`) the operator —
    or a future Claude session — can scan top to bottom.

    Exits 0 if every check is OK or WARN; 1 if any FAIL fired."""
    import shutil
    import subprocess

    workspace = Path.cwd()
    fails = 0

    def line(status: str, msg: str) -> None:
        nonlocal fails
        if status == "FAIL":
            fails += 1
        print(f"  [{status:>4}] {msg}")

    print("\n=== External tools ===")
    # Claude CLI
    if shutil.which("claude"):
        try:
            r = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
            v = (r.stdout or "").strip().splitlines()[0] if r.stdout else "?"
            line("OK", f"claude  {v}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            line("FAIL", f"claude --version timed out or errored: {exc}")
    else:
        line("WARN", "claude CLI not on PATH (Claude provider unavailable)")

    # Gemini CLI — use the same Windows-aware resolver the provider does
    # (npm ships gemini as a bash shim + gemini.cmd; subprocess.run on
    # Windows can only launch the .cmd).
    from ..llm.gemini_cli import resolve_gemini_executable
    gemini_exe = resolve_gemini_executable()
    if gemini_exe:
        try:
            r = subprocess.run(
                [gemini_exe, "--version"],
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
            )
            v = (r.stdout or "").strip().splitlines()[0] if r.stdout else "?"
            line("OK", f"gemini  {v}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            line("FAIL", f"gemini --version timed out or errored: {exc}")
    else:
        line("WARN", "gemini CLI not on PATH (Gemini provider unavailable)")

    # Lake (Lean build tool)
    if shutil.which("lake"):
        try:
            r = subprocess.run(
                ["lake", "env", "lean", "--version"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            v = (r.stdout or "").strip().splitlines()[0] if r.stdout else "?"
            line("OK", f"lake env lean  {v}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            line("FAIL", f"lake env lean errored: {exc}")
    else:
        line("FAIL", "lake not on PATH — cannot build Lean (mandatory)")

    # Asterism.yaml
    print("\n=== Asterism.yaml ===")
    cfg_path = workspace / "Asterism.yaml"
    if not cfg_path.exists():
        line("WARN", f"{cfg_path.name} absent — using built-in defaults "
                     f"(see docs/architecture.md §10 for schema)")
    else:
        try:
            from . import config as _config
            _config._reset_cache()
            data = _config.load(workspace)
            keys = []
            for top in ("dispatch", "builder", "backward"):
                if top in data and isinstance(data[top], dict):
                    keys.append(f"{top}({len(data[top])})")
            line("OK", f"{cfg_path.name}: " + ", ".join(keys)
                       if keys else f"{cfg_path.name}: empty / no known sections")
        except Exception as exc:
            line("FAIL", f"{cfg_path.name} parse error: {exc}")

    # Problems
    print("\n=== Problems ===")
    conn = db.connect()
    db.init_schema(conn)
    rows = conn.execute(
        "SELECT name, manifest_path FROM problems ORDER BY name"
    ).fetchall()
    if not rows:
        line("WARN", "no problems initialized — run `asterism init <p>`")
    for r in rows:
        name = r["name"]
        mfst_path = workspace / r["manifest_path"]
        if not mfst_path.exists():
            line("FAIL", f"{name}: Manifest.md missing at {r['manifest_path']}")
            continue
        try:
            mfst = manifest.parse(mfst_path)
            if not mfst.statement:
                line("FAIL", f"{name}: Manifest.md has no `## Statement` section")
                continue
        except Exception as exc:
            line("FAIL", f"{name}: Manifest parse error: {exc}")
            continue
        # Root goal status
        root = conn.execute(
            "SELECT id, status, attempts FROM goals "
            "WHERE problem = ? AND slug = 'main'", (name,)
        ).fetchone()
        if root:
            line("OK", f"{name}: root goal id={root['id']} "
                       f"status={root['status']} attempts={root['attempts']}")
        else:
            line("WARN", f"{name}: registered but no root goal "
                         f"(re-run `asterism init {name}`)")

    # Filesystem state
    print("\n=== Filesystem state ===")
    attempts_dir = workspace / ".attempts"
    if attempts_dir.exists():
        n = sum(1 for _ in attempts_dir.iterdir())
        if n > 5:
            line("WARN", f".attempts/ has {n} dirs — likely zombies, "
                         f"`rm -rf .attempts/` after killing daemon")
        elif n:
            line("OK", f".attempts/ has {n} dir(s) — possibly live or recent")
        else:
            line("OK", ".attempts/ empty")
    else:
        line("OK", ".attempts/ does not exist (clean state)")

    log_dir = workspace / LOG_DIR
    if log_dir.exists():
        logs = list(log_dir.glob("*.log"))
        total = sum(p.stat().st_size for p in logs) if logs else 0
        line("OK", f".asterism/logs/  {len(logs)} file(s), "
                   f"{total // 1024} KB")

    print()
    print(f"=== Summary: {fails} FAIL ===" if fails else
          "=== Summary: all checks passed (some WARN OK) ===")
    return 0 if fails == 0 else 1


def _parse_library_index(path: Path) -> "dict[str, set[tuple[str, str]]]":
    """Parse `Library/INDEX.md` into `{problem: {(decl_name, relpath), ...}}`.

    Section header line is `## <problem>`; each entry line carries exactly two
    backtick-quoted tokens — `` - `<name>` → `<relpath>` `` (the arrow glyph is
    not load-bearing, so we read the backtick tokens, not the separator).
    Returns {} if the file is absent."""
    out: "dict[str, set[tuple[str, str]]]" = {}
    if not path.exists():
        return out
    cur: "str | None" = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if raw.startswith("## "):
            cur = raw[3:].strip()
            out.setdefault(cur, set())
        elif cur is not None and raw.lstrip().startswith("- `"):
            toks = re.findall(r"`([^`]+)`", raw)
            if len(toks) >= 2:
                out[cur].add((toks[0], toks[1]))
    return out


def _library_consistency_findings(conn, workspace: Path
                                  ) -> "list[tuple[str, str]]":
    """INDEX <-> disk <-> DB consistency over the *placed* decl set.

    "Placed" = `library_decls.lifecycle IN ('migrated','cleaned')` — exactly
    the set `_harvested_decls`/INDEX record. 'cited'/'dropped'/'classified'
    decls are NOT placed (no file contribution), so they never participate.
    Mirrors the problem-side recovery orphan-sweep, but for `Library/`.

    Printer-free on purpose: returns `[(status, message), ...]` with status in
    {OK, WARN, FAIL} so the caller prints/exits and tests assert on findings.
    Severity rationale:
      - DB row -> missing file / orphan disk file / INDEX -> missing file:
        hard breaks (a citer is misled, or a file nothing owns lingers) -> FAIL.
      - INDEX section exists but disagrees with DB placed-set (either way):
        stale provenance -> FAIL.
      - DB has placed decls but NO INDEX section: not yet bridged (legit
        mid-flight) -> WARN."""
    out: "list[tuple[str, str]]" = []
    lib = workspace / "Library"

    placed = conn.execute(
        "SELECT problem, target_name, target_file, slug, lifecycle "
        "FROM library_decls WHERE lifecycle IN ('migrated','cleaned')"
    ).fetchall()
    db_files = {r["target_file"] for r in placed if r["target_file"]}
    db_by_problem: "dict[str, set[tuple[str, str]]]" = {}
    for r in placed:
        name = r["target_name"] or r["slug"]
        db_by_problem.setdefault(r["problem"], set()).add(
            (name, r["target_file"] or "?"))

    disk_files = {p.relative_to(workspace).as_posix()
                  for p in lib.rglob("*.lean")}

    # I1 — every DB-placed file exists on disk.
    missing = sorted(f for f in db_files if f not in disk_files)
    for f in missing:
        out.append(("FAIL", f"DB places a decl in a missing file: {f}"))
    if not missing:
        out.append(("OK", f"{len(db_files)} DB-placed file(s) present on disk"))

    # I2 — every on-disk Library file is owned by a placed DB decl (orphan).
    orphans = sorted(f for f in disk_files if f not in db_files)
    for f in orphans:
        out.append(("FAIL", f"orphan Library file (no placed DB decl): {f}"))
    if not orphans:
        out.append(("OK", f"{len(disk_files)} on-disk file(s) all DB-owned"))

    # I3 — every INDEX entry's file exists on disk.
    index_by_problem = _parse_library_index(lib / "INDEX.md")
    index_relpaths = {rp for s in index_by_problem.values() for (_, rp) in s}
    idx_missing = sorted(rp for rp in index_relpaths
                         if rp != "?" and rp not in disk_files)
    for rp in idx_missing:
        out.append(("FAIL", f"INDEX entry points to a missing file: {rp}"))
    if not idx_missing:
        out.append(("OK", f"{len(index_relpaths)} INDEX file ref(s) present"))

    # I4 — per problem, INDEX section == DB placed-set.
    for prob in sorted(set(index_by_problem) | set(db_by_problem)):
        idx = index_by_problem.get(prob, set())
        dbp = db_by_problem.get(prob, set())
        if idx == dbp:
            out.append(("OK", f"{prob}: INDEX matches DB ({len(idx)} decl(s))"))
        elif dbp and not idx:
            out.append(("WARN", f"{prob}: {len(dbp)} placed decl(s) but no "
                                f"INDEX section (not yet bridged?)"))
        elif idx and not dbp:
            out.append(("FAIL", f"{prob}: INDEX section present but no placed "
                                f"DB decls (fully stale INDEX)"))
        else:
            out.append(("FAIL", f"{prob}: INDEX/DB placed-set mismatch "
                                f"(+{len(idx - dbp)} INDEX-only, "
                                f"+{len(dbp - idx)} DB-only)"))

    # I5 — a CLEANED file should carry no `import Mathlib` umbrella. decide
    # minimises imports mechanically (`#import_bumps`); a surviving umbrella is
    # the rare degraded fallback (the linter could not produce a buildable set)
    # — non-idiomatic and rejected by a mathlib PR. WARN, not FAIL: the file
    # still builds, so this surfaces the defect without blocking the gate.
    # 'migrated'-but-not-'cleaned' files legitimately still carry it (mid-flight).
    cleaned_files = sorted({r["target_file"] for r in placed
                            if r["target_file"] and r["lifecycle"] == "cleaned"})
    umbrella = []
    for f in cleaned_files:
        try:
            txt = (workspace / f).read_text(encoding="utf-8")
        except OSError:
            continue
        if any(ln.strip() == "import Mathlib" for ln in txt.splitlines()):
            umbrella.append(f)
    for f in umbrella:
        out.append(("WARN", f"cleaned file keeps the `import Mathlib` umbrella "
                            f"(decide import-min degraded to fallback): {f}"))
    if cleaned_files and not umbrella:
        out.append(("OK", f"{len(cleaned_files)} cleaned file(s) carry precise "
                          f"imports (no `import Mathlib` umbrella)"))
    return out


def cmd_library_verify(args: argparse.Namespace) -> int:
    """Whole-Library coherence gate (P1). Two mechanical checks, no agent:

      (B) INDEX <-> disk <-> DB consistency over the placed decl set — orphan
          files, DB rows pointing at missing files, stale INDEX provenance.
          Mirrors the problem-side recovery orphan-sweep.
      (A) `lake build Library` — the whole placed Library compiles together.
          The per-file / per-problem bridge gates only ever see ONE problem's
          files, so a cross-problem breakage is invisible to them; this is the
          missing whole-Library view, and the precondition for any future
          Library rewrite (cross-problem rewire): you cannot safely edit a
          cross-cited shared lemma without proving every downstream consumer
          still builds.

    Output is icon-prefixed `[OK/FAIL/WARN]` lines (same shape as `doctor`).
    Exit 0 if every check is OK/WARN; 1 if any FAIL. `--no-build` runs the
    fast consistency-only pass (skips A)."""
    import shutil
    import subprocess

    workspace = Path.cwd()
    fails = 0

    def line(status: str, msg: str) -> None:
        nonlocal fails
        if status == "FAIL":
            fails += 1
        print(f"  [{status:>4}] {msg}")

    if not (workspace / "Library").exists():
        print("Library/ absent — nothing to verify")
        return 0

    print("\n=== Consistency (INDEX <-> disk <-> DB) ===")
    conn = db.connect()
    db.init_schema(conn)
    for status, msg in _library_consistency_findings(conn, workspace):
        line(status, msg)

    if args.no_build:
        print("\n=== Whole-Library build: SKIPPED (--no-build) ===")
    else:
        print("\n=== Whole-Library build (`lake build Library`) ===")
        if not shutil.which("lake"):
            line("FAIL", "lake not on PATH — cannot build Library")
        else:
            try:
                r = subprocess.run(
                    ["lake", "build", "Library"],
                    cwd=str(workspace), capture_output=True, text=True,
                    timeout=args.build_timeout,
                    encoding="utf-8", errors="replace",
                )
                if r.returncode == 0:
                    line("OK", "lake build Library succeeded")
                else:
                    # Surface the REAL Lean errors, not lake's terminal
                    # "error: build failed" summary: scan both streams for
                    # `error:` lines (the unresolved-reference / type errors a
                    # cross-problem breakage shows up as), and only fall back
                    # to the tail when none are present.
                    both = ((r.stdout or "") + "\n" + (r.stderr or "")).splitlines()
                    errs = [ln.strip() for ln in both
                            if "error:" in ln and "build failed" not in ln]
                    shown = errs[:5] or [ln.strip() for ln in both
                                         if ln.strip()][-5:]
                    snippet = " | ".join(shown)[:800]
                    line("FAIL", f"lake build Library failed "
                                 f"(rc={r.returncode}): {snippet or '(no output)'}")
            except subprocess.TimeoutExpired:
                line("FAIL", f"lake build Library timed out "
                             f"(>{args.build_timeout}s)")
            except OSError as exc:
                line("FAIL", f"lake build Library errored: {exc}")

    print()
    print(f"=== Summary: {fails} FAIL ===" if fails else
          "=== Summary: all checks passed (some WARN OK) ===")
    return 0 if fails == 0 else 1


def cmd_review(args: argparse.Namespace) -> int:
    """anchor+claim review surface (docs/internal/anchor_claim_design.md).

    For every goal the Strategist marked `is_deliverable=1` (optionally
    scoped by `problem`), compute its kernel anchor closure and present
    the anchors (defs the human must vouch for) + claims (lemmas the
    closure rests on), partitioned. Reject an entry with
    `asterism reject <decl>` (Phase 3).

    Read-only. Needs the gateway (reused if already warm; else warmed —
    slow on a cold Mathlib cache). Exit 0 always (a review, not a gate);
    deliverables whose closure could not be computed print a WARN."""
    from ..lsp import lifecycle as gateway_lifecycle
    from ..pipeline._constants import anchor_closure_goal

    workspace = Path.cwd()
    conn = db.connect()
    db.init_schema(conn)
    scope = getattr(args, "problem", None)
    dels = db.deliverables(conn, problem=scope)
    conn.close()

    if not dels:
        where = f" for '{scope}'" if scope else ""
        print(f"no deliverables{where} (Strategist marks them via "
              f"is_deliverable; none set yet)")
        return 0

    gateway_lifecycle.start_gateway(workspace)

    def render(items: list[dict], head: str) -> None:
        if not items:
            return
        print(f"    {head}")
        for c in sorted(items, key=lambda x: x["name"]):
            mod = c.get("module") or "<local>"
            print(f"      - {c['name']}   ({mod})")

    print(f"\n=== anchor+claim review: {scope or 'all problems'} ===")
    union: set[str] = set()
    for g in dels:
        dest = workspace / g["lean_path"]
        r = anchor_closure_goal(
            workspace, dest, problem=g["problem"], slug=g["slug"])
        fq = f"Problems.{g['problem']}.{g['slug']}"
        if not r.ok:
            print(f"\n▸ {fq}  [WARN] closure unavailable: {r.error}")
            continue
        kind = "claim" if r.top_is_claim else f"anchor:{r.top_kind}"
        print(f"\n▸ {fq}  [{kind}]   (module {r.top_module or '<local>'})")
        if not r.pending:
            print("    (no pending anchors — statement rests entirely on "
                  "Mathlib ∪ Library)")
        render(r.anchors, "anchors (defs you must vouch for):")
        render(r.claims, "claims (lemmas the closure rests on):")
        union.update(c["name"] for c in r.pending)

    print(f"\n=== {len(dels)} deliverable(s), {len(union)} distinct "
          f"pending anchor(s)/claim(s) ===")
    return 0


def _resolve_reject_target(conn, decl: str, problem: str | None):
    """Resolve a `<decl>` (bare slug or `Problems.<problem>.<slug>` FQN,
    as printed by `asterism review`) to its goal row. Returns
    (goal_row | None, error_msg | None)."""
    slug = decl
    if decl.startswith("Problems."):
        body = decl[len("Problems."):]
        parts = body.rsplit(".", 1)
        if len(parts) == 2:
            problem, slug = parts[0], parts[1]
    if problem:
        g = db.goal_by_slug(conn, problem, slug)
        return g, (None if g else f"no goal {slug!r} in {problem!r}")
    rows = conn.execute("SELECT * FROM goals WHERE slug = ?", (slug,)).fetchall()
    if len(rows) > 1:
        probs = sorted({r["problem"] for r in rows})
        return None, f"ambiguous slug {slug!r} across {probs}; pass --problem"
    return (rows[0] if rows else None), (None if rows else f"no goal {slug!r}")


def _find_reject_victims(conn, workspace, *, reject_gid, problem, fqn,
                         closure_fn):
    """Deliverables (in `problem`) whose statement closure contains the
    rejected `fqn`. `closure_fn(workspace, dest, problem=, slug=)` →
    AnchorClosure (injected for testing). Returns (victims, warnings)
    where victims is [(goal_id, fqn), ...] and warnings is
    [(slug, error), ...] for deliverables whose closure couldn't be
    computed (conservatively NOT cascaded through)."""
    victims: list[tuple[int, str]] = []
    warnings: list[tuple[str, str]] = []
    for d in db.deliverables(conn, problem=problem):
        did = int(d["id"])
        if did == reject_gid:
            continue
        r = closure_fn(workspace, workspace / d["lean_path"],
                       problem=d["problem"], slug=d["slug"])
        if not r.ok:
            warnings.append((str(d["slug"]), str(r.error)))
            continue
        if any(c["name"] == fqn for c in r.pending):
            victims.append((did, f"Problems.{d['problem']}.{d['slug']}"))
    return victims, warnings


def cmd_reject(args: argparse.Namespace) -> int:
    """anchor+claim reject (docs/internal/anchor_claim_design.md §2.5).

    Kill a rejected framework-generated node AND every deliverable whose
    STATEMENT's meaning depends on it — computed by inverting the Phase-1
    kernel anchor closure (a deliverable is a victim iff the rejected decl
    is in its closure). Only meaning-dependencies cascade: a deliverable
    that merely cites the node in its PROOF (statement independent) keeps
    its meaning and is left alone. Re-wakes the Strategist to re-plan
    (the reject reason rides the producing Inject's outcome_detail).

    Only Forward-produced nodes are rejectable — a hand-written root/Defs
    is author-vouched. `--dry-run` previews the cascade without mutating.
    Needs the gateway (reused if warm)."""
    from ..lsp import lifecycle as gateway_lifecycle
    from ..pipeline._constants import anchor_closure_goal
    from ..state import transitions

    workspace = Path.cwd()
    conn = db.connect()
    db.init_schema(conn)

    g, err = _resolve_reject_target(conn, args.decl, getattr(args, "problem", None))
    if err:
        print(err)
        return 1
    if str(g["origin"]) != "forward":
        print(f"cannot reject {args.decl!r}: origin={g['origin']!r} — only "
              f"Forward-generated nodes are rejectable (hand-written "
              f"root/Defs are author-vouched).")
        return 1

    gid = int(g["id"])
    gproblem = str(g["problem"])
    fqn = f"Problems.{gproblem}.{g['slug']}"
    reason = getattr(args, "reason", None) or "(no reason given)"

    # Reverse cascade: deliverables whose statement closure contains fqn.
    # Probe against the on-disk files (unchanged by the DB status flips),
    # so order relative to the kill doesn't matter.
    gateway_lifecycle.start_gateway(workspace)
    victims, warnings = _find_reject_victims(
        conn, workspace, reject_gid=gid, problem=gproblem, fqn=fqn,
        closure_fn=anchor_closure_goal)
    for slug, cerr in warnings:
        print(f"  [WARN] {slug}: closure unavailable ({cerr}); cannot tell "
              f"if it depends on {fqn} — not cascading through it")

    if getattr(args, "dry_run", False):
        print(f"[dry-run] would reject {fqn} ({g['kind']}) + cascade-kill "
              f"{len(victims)} dependent deliverable(s):")
        for _, vfqn in victims:
            print(f"    - {vfqn}")
        conn.close()
        return 0

    # Kill the rejected node.
    transitions._set_goal_terminal_and_propagate(conn, gid, "dead")
    db.mark_deliverable(conn, gid, False)
    db.set_inject_outcome_detail(conn, gid, f"human rejected: {reason}")
    # Kill the meaning-dependent deliverables.
    for did, _vfqn in victims:
        transitions._set_goal_terminal_and_propagate(conn, did, "dead")
        db.mark_deliverable(conn, did, False)
        db.set_inject_outcome_detail(
            conn, did, f"depends on rejected anchor {fqn}: {reason}")

    print(f"rejected {fqn} + {len(victims)} dependent deliverable(s): "
          f"{[v for _, v in victims]}")
    print("Strategist re-plans on its next wake (inject_batch_done); the "
          "reject reason rides each node's outcome_detail.")
    conn.close()
    return 0


def cmd_drift_check(args: argparse.Namespace) -> int:
    """DB<->file consistency gate (`proof_store.inventory`) — the single oracle
    for the drift class the proof_store chokepoint prevents: orphan proof files
    (no DB row), missing files (a goal past 'open' whose file is gone), and
    proved-with-sorry (a `status='proved'` goal whose file carries a `sorry`).
    Exit 0 if consistent, 1 on any drift. `--scope` limits to a problem (LIKE)."""
    from ..state import proof_store
    workspace = Path.cwd()
    conn = db.connect()
    try:
        rep = proof_store.inventory(
            conn, workspace, scope=getattr(args, "scope", None))
    finally:
        conn.close()
    for rel in rep.orphan_files:
        print(f"  [FAIL] orphan proof file (no DB row): {rel}")
    for rel in rep.missing_files:
        print(f"  [FAIL] missing proof file (row past 'open'): {rel}")
    for rel in rep.proved_with_sorry:
        print(f"  [FAIL] proved goal's file carries `sorry`: {rel}")
    print(f"  [{'  OK' if rep.ok() else 'FAIL'}] {rep.summary()}")
    return 0 if rep.ok() else 1


def cmd_logs(args: argparse.Namespace) -> int:
    """List / tail framework run logs from `.asterism/logs/`.
    Default: list with sizes, mtime, sorted newest first.
    `--tail N`: print the last N lines of the most recent log.
    """
    workspace = Path.cwd()
    log_dir = workspace / LOG_DIR
    if not log_dir.exists():
        print(f"no log dir at {log_dir}")
        return 0
    logs = sorted(log_dir.glob("*.log"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        print(f"no logs in {log_dir}")
        return 0
    if args.tail:
        latest = logs[0]
        print(f"# {latest.name}  ({latest.stat().st_size:,} bytes)")
        with latest.open("r", encoding="utf-8", errors="replace") as f:
            tail_lines = f.readlines()[-args.tail:]
        sys.stdout.writelines(tail_lines)
        return 0
    print(f"# {log_dir} ({len(logs)} logs)")
    for p in logs:
        st = p.stat()
        ts = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {st.st_size:>8,} B  {ts}  {p.name}")
    return 0


def cmd_config(args: argparse.Namespace) -> int:
    """Print the resolved Asterism config — what `dispatch.*`,
    `builder.*`, `backward.*` actually evaluate to right now (env >
    Asterism.yaml > legacy env > built-in default). Eliminates
    "what's actually active?" confusion when env vars + yaml + defaults
    interact.
    """
    from . import config as _cfg
    from ..llm import claude_cli as _cc
    rows = [
        ("dispatch.pool",
         _cfg.get("dispatch.pool", env_var="ASTERISM_POOL", default=12, cast=int)),
        ("dispatch.budget_sec",
         _cfg.get("dispatch.budget_sec", env_var="ASTERISM_BUDGET_SEC",
                  default=1800, cast=int)),
        ("dispatch.shelve_threshold",
         _cfg.get("dispatch.shelve_threshold",
                  env_var="ASTERISM_SHELVE_THRESHOLD", default=8, cast=int)),
        ("builder.threshold",
         _cfg.get("builder.threshold",
                  legacy_env=("ASTERISM_BUILDER_THRESHOLD",),
                  default=_cfg.get("dispatch.builder_threshold", default=3, cast=int),
                  cast=int)),
        ("builder.model", _cc.resolve_model("builder")),
        ("backward.model", _cc.resolve_model("backward")),
    ]
    for k, v in rows:
        print(f"  {k:<30} = {v}")
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    """Manual fallback: GC orphan lean files in proofs/. Auto-invoked by
    `run` on success; this CLI exists for partial state (user killed
    daemon mid-run / run hit budget without proving root)."""
    workspace = Path.cwd()
    conn = db.connect()
    if args.problem:
        problems = [args.problem]
    else:
        problems = [r["name"] for r in conn.execute("SELECT name FROM problems")]

    total_removed = 0
    for p in problems:
        # Reconcile first to fix any file/DB drift, then prune orphans.
        # Skip reconcile under --dry-run since reconcile mutates files.
        if not args.dry_run:
            repaired = prune.reconcile_proved_goals(conn, workspace, p)
            if repaired:
                print(f"[reconcile] {p}: repaired {len(repaired)} drifted files")
        try:
            removed = prune.prune_problem(conn, workspace, p,
                                          dry_run=args.dry_run,
                                          force=args.force)
        except RuntimeError as exc:
            print(f"[prune] {p}: REFUSED — {exc}", flush=True)
            continue
        total_removed += len(removed)
        verb = "would remove" if args.dry_run else "removed"
        if removed:
            print(f"[prune] {p}: {verb} {len(removed)} orphan files")
            for f in removed:
                print(f"  {f.relative_to(workspace).as_posix()}")
        else:
            print(f"[prune] {p}: nothing to remove "
                  f"(root not proved, or already clean)")
    return 0


def _force_utf8_io() -> None:
    """Force UTF-8 for this process's console I/O and for every spawned
    subprocess. On a locale-default (e.g. cp950 Traditional-Chinese)
    Windows console, emitting a char outside that codepage — a Lean goal
    routinely carries `∃` (U+2203), `∀`, `≃ᵢ`, etc. — raised
    UnicodeEncodeError mid-pipeline and was mis-recorded as a spurious
    lake_build_error (BT 2026-05-29 g3410 exists_rotation_shift_disjoint:
    3 of 5 attempts died on `cp950 can't encode '\\u2203'`, blocking a
    goal that was otherwise fine). Every framework file write already
    pins encoding='utf-8'; the gap was the inherited console encoding and
    child-process default. Reconfiguring stdout/stderr fixes this
    process's prints (and the _Tee that wraps them); exporting
    PYTHONUTF8 / PYTHONIOENCODING makes claude / lake / gateway children
    inherit UTF-8 so they don't reintroduce the crash one layer down.

    Idempotent and safe under pytest's captured streams (reconfigure is
    skipped when the stream doesn't support it)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="backslashreplace")
            except (ValueError, OSError):
                pass
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def cmd_kb_migrate(args: argparse.Namespace) -> int:
    """Rebuild the mechanically-derivable KB entries (antipatterns) from
    `.drafts` blockers + `dead_attempts` rationale. Idempotent (source-keyed),
    safe to re-run. Lessons are NOT rebuilt here — under Model B they are
    live-authored by the reflection spawn (KB is the source of truth; the old
    flat-`LESSONS.md` mirror is gone), so they have no mechanical source."""
    workspace = Path.cwd()
    conn = db.connect()
    db.init_schema(conn)
    try:
        antis = kb_ingest.ingest_antipatterns(conn, workspace)
        total = conn.execute("SELECT COUNT(*) FROM kb_entries").fetchone()[0]
    finally:
        conn.close()
    print(f"OK: kb-migrate — {antis} antipattern(s) ingested; "
          f"{total} kb_entries total")
    return 0


def main(argv: list[str] | None = None) -> int:
    _force_utf8_io()
    parser = argparse.ArgumentParser(prog="asterism")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="initialize a Problem")
    p_init.add_argument("problem", help="problem name (Problems/<problem>/)")
    p_init.add_argument(
        "--force", action="store_true",
        help="bypass the Root.lean-shape guard (allows hand-written sketches)",
    )
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="run dispatcher")
    p_run.add_argument("--once", action="store_true",
                       help="exit when queue empties")
    p_run.add_argument(
        "--scope", type=str, default=None,
        help="restrict dispatch to problems matching this SQL LIKE "
             "pattern (e.g. 'minif2f_%%'). Other problems' goals stay "
             "in their current state but are not dispatched this run.",
    )
    p_run.add_argument(
        "--all-problems", action="store_true",
        help="explicitly opt into a WORKSPACE-WIDE run (dispatch + "
             "recovery orphan-sweep across EVERY problem). Required when "
             "--scope is omitted: a no-scope run is rarely intended and "
             "touches all problems, so it is refused without this flag.",
    )
    p_run.set_defaults(func=cmd_run)

    p_init_batch = sub.add_parser(
        "init-batch",
        help="bulk-init every <root>/<subdir>/ that has a Manifest.md",
    )
    p_init_batch.add_argument(
        "root", help="directory whose immediate subdirs are problem dirs",
    )
    p_init_batch.set_defaults(func=cmd_init_batch)

    p_reset = sub.add_parser(
        "reset",
        help="wipe a Problem's DB rows + proof files + Root.lean stub",
    )
    p_reset.add_argument("problem", help="problem name")
    p_reset.add_argument(
        "--soft", action="store_true",
        help="surgical: only clear spurious dead_attempts + revive "
             "cascade victims (use after a quota-exhaust incident)",
    )
    p_reset.set_defaults(func=cmd_reset)

    p_status = sub.add_parser(
        "status",
        help="show goals / strategies / dead_attempts / pipelines for a Problem",
    )
    p_status.add_argument("problem", help="problem name")
    p_status.add_argument(
        "--json", action="store_true",
        help="emit JSON instead of human-readable text",
    )
    p_status.set_defaults(func=cmd_status)

    p_doctor = sub.add_parser(
        "doctor",
        help="pre-flight: tools / Asterism.yaml / Manifests / .attempts state",
    )
    p_doctor.set_defaults(func=cmd_doctor)

    p_libverify = sub.add_parser(
        "library-verify",
        help="whole-Library coherence gate: INDEX<->disk<->DB consistency "
             "+ `lake build Library`",
    )
    p_libverify.add_argument(
        "--no-build", action="store_true",
        help="skip `lake build Library` (fast consistency-only pass)")
    p_libverify.add_argument(
        "--build-timeout", type=int, default=1800, metavar="SEC",
        help="timeout (seconds) for `lake build Library` (default 1800)")
    p_libverify.set_defaults(func=cmd_library_verify)

    p_review = sub.add_parser(
        "review",
        help="anchor+claim review: kernel anchor closure of each "
             "Strategist-marked deliverable (anchors to vouch for)")
    p_review.add_argument("problem", nargs="?", default=None,
                          help="optional; default = deliverables across all problems")
    p_review.set_defaults(func=cmd_review)

    p_reject = sub.add_parser(
        "reject",
        help="anchor+claim reject: kill a Forward node + every deliverable "
             "whose meaning depends on it (reverse anchor closure)")
    p_reject.add_argument("decl",
                          help="slug or Problems.<problem>.<slug> FQN (as `review` prints)")
    p_reject.add_argument("--problem", default=None,
                          help="disambiguate a bare slug shared across problems")
    p_reject.add_argument("--reason", default=None,
                          help="why (rides the Strategist's next wake); optional")
    p_reject.add_argument("--dry-run", action="store_true",
                          help="preview the cascade without mutating")
    p_reject.set_defaults(func=cmd_reject)

    p_drift = sub.add_parser(
        "drift-check",
        help="DB<->file consistency gate (orphan / missing / proved-with-sorry)")
    p_drift.add_argument(
        "--scope", type=str, default=None, metavar="PROBLEM",
        help="limit to a problem (LIKE pattern), e.g. residue_thm")
    p_drift.set_defaults(func=cmd_drift_check)

    p_prune = sub.add_parser(
        "prune",
        help="GC orphan lean files in proofs/ (auto-runs on successful run)",
    )
    p_prune.add_argument("problem", nargs="?",
                         help="optional; default = all problems")
    p_prune.add_argument("--dry-run", action="store_true",
                         help="list files without deleting")
    p_prune.add_argument("--force", action="store_true",
                         help="bypass integrity_verified gate "
                              "(use only when axiom_probe is known broken)")
    p_prune.set_defaults(func=cmd_prune)

    p_logs = sub.add_parser(
        "logs",
        help="list / tail framework run logs (.asterism/logs/)",
    )
    p_logs.add_argument("--tail", type=int, metavar="N",
                        help="print last N lines of the most recent log "
                             "instead of listing")
    p_logs.set_defaults(func=cmd_logs)

    p_config = sub.add_parser(
        "config",
        help="print resolved Asterism config (env > yaml > legacy > default)",
    )
    p_config.set_defaults(func=cmd_config)

    p_kb_migrate = sub.add_parser(
        "kb-migrate",
        help="re-ingest mechanically-derived KB antipatterns from .drafts "
             "blockers + dead_attempts rationale (idempotent, source-keyed)",
    )
    p_kb_migrate.set_defaults(func=cmd_kb_migrate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
