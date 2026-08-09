"""CLI: asterism init <p> | asterism run [--once] | asterism reset <p>
       | asterism status <p> [--json] | asterism prune [<p>] [--dry-run]
       | asterism library-verify [--no-build].

See docs/architecture.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path

from ..state import brief, db, kb, kb_ingest, manifest, tree
from . import dispatcher, fsutil
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
    """`<problem>_<UTC ts>.log` — `<problem>` falls back to `daemon`
    when the DB has no problems yet (e.g. first run before init), or
    `multi` when more than one problem is registered.

    No model in the name any more. It used to carry one, resolved from
    `builder` + `backward` — two keys the v33 Formalizer merge retired,
    so both fell through to DEFAULT_MODEL and the label named a model
    that had nothing to do with the run: 2026-08-06's log is
    `multi_claude-sonnet-4-6_…` for a run whose formalizer was
    gemini-3.6-flash-high and whose strategist was claude-opus-5. That
    is worse than no label, because the run's timing analyses are
    identified BY these filenames.

    A single token cannot honestly name a run with one model per seat,
    so the seats go where they fit: `seat_banner()` writes the whole
    table into the log's first lines, where it is accurate by
    construction and stays accurate when a seat moves mid-run.
    """
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
    return f"{problem}_{_utc_log_stamp()}.log"


def seat_banner() -> str:
    """The run's actual seats, for the head of its log.

    What the filename cannot say: one line per pipeline that spawns a
    model, with the provider and model it is configured to use right
    now. This is what a later timing or A/B analysis needs to know it is
    comparing like with like — and reading it off a filename is how a
    run gets attributed to a model it never used.
    """
    from . import dispatcher
    try:
        seats = dispatcher._pipeline_seats()
    except Exception:  # noqa: BLE001 — a banner must never block a run
        return "[seats] unavailable"
    return "\n".join(
        [f"[seats] {kind}: {prov}/{model or '(provider default)'}"
         for kind, (prov, model) in sorted(seats.items())])


def _utc_log_stamp() -> str:
    """UTC timestamp for log filenames, `Z`-suffixed. Local-time names
    beside UTC DB timestamps mis-billed a 5h15m outage as 14.7 min
    (2026-07-19) — one clock, self-documented."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "Z"


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
#  on root proved — the proof lands IN Root.lean via one of two sanctioned
#                   writers: a Builder assembly commits the full
#                   `theorem main : <stmt> := by …` (statement preserved
#                   byte-for-byte), or Verify promote / `prune.
#                   reconcile_proved_goals` write the def-alias form:
#                   `import Problems.X.proofs._strategy_sNN` then
#                   `def main := @Problems.X.sNN` (any leading
#                   `@[instance]` is preserved). Both shapes are accepted
#                   by `verify._root_statement_pin_ok` (task #120) —
#                   the user-file pin guards the STATEMENT, not the bytes.
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

# Statement extraction (`theorem main : <stmt> := by sorry` → `<stmt>`)
# moved to state/manifest.py (task #120: the root gate's statement pin
# must read the exact same bytes cmd_init/amend extract). Re-exported
# under the old names for the existing importers (amend, tests).
_ROOT_STATEMENT_RE = manifest.ROOT_STMT_STUB_RE
_extract_root_statement = manifest.extract_root_statement


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


def cmd_init(args: argparse.Namespace) -> int:
    rc, msg = init_problem(
        Path.cwd(), args.problem, force=bool(getattr(args, "force", False)))
    print(msg, file=sys.stdout if rc == 0 else sys.stderr)
    return rc


def delete_problem(workspace: Path, problem: str) -> tuple[int, str]:
    """Delete a problem ENTIRELY — every DB row AND the whole
    Problems/<p>/ directory, in one chokepoint (rule 10: files and DB
    move together; shared by the CLI and the serve API).

    Guards, enforced HERE and not just in a UI:
      - a Library-bridged problem refuses: its chapter files import
        Problems.<p>.proofs.* and deleting them breaks the Library
        build — un-harvest first (rc 2).
      - a daemon currently working this problem refuses (rc 3).
    """
    import shutil
    import time
    pdir = db.problem_dir(workspace, problem)
    conn = db.connect(workspace / "asterism.db")
    try:
        db.init_schema(conn)
        conn.execute("PRAGMA foreign_keys = ON")
        row = conn.execute(
            "SELECT library_bridged_at FROM problems WHERE name = ?",
            (problem,)).fetchone()
        in_db = row is not None
        if not in_db and not pdir.exists():
            return 1, f"unknown problem {problem!r}"
        if row and row["library_bridged_at"]:
            return 2, (f"{problem} is in the Library — its chapter imports"
                       " these proofs; un-harvest it first")
        st = daemon_status(workspace)
        if st.get("running") and st.get("scope") == problem:
            return 3, "the engine is working this problem — stop the run first"
        if in_db:
            wipe_problem_rows(conn, problem)
            conn.commit()
    finally:
        conn.close()
    if pdir.exists():
        # Windows file locks (a just-exited lean/claude tree) clear in
        # seconds — retry, then report honestly instead of half-deleting
        last: "Exception | None" = None
        for attempt in range(4):
            try:
                shutil.rmtree(pdir)
                last = None
                break
            except OSError as e:
                last = e
                time.sleep(0.5 * (attempt + 1))
        if last is not None:
            return 4, (f"DB rows removed, but Problems/{problem}/ is locked"
                       f" ({last}) — close whatever holds it and delete the"
                       " folder by hand")
    return 0, f"deleted {problem}"


def init_problem(workspace: Path, problem: str, *,
                 force: bool = False) -> tuple[int, str]:
    """Validate + register a problem (chokepoint shared by CLI + serve).

    Expects `Problems/<problem>/Manifest.md` to exist (Defs.lean /
    Root.lean optional — see the Phase 6 comment below). Returns
    (0, ok-message) or (1, failure-message); never prints.
    """
    msgs: list[str] = []
    pdir = db.problem_dir(workspace, problem)
    mfst_path = pdir / "Manifest.md"
    if not mfst_path.exists():
        return 1, f"FAIL: {mfst_path} not found"

    try:
        mfst = manifest.parse(mfst_path)  # Statement section now optional
    except Exception as e:  # noqa: BLE001 — malformed authoring input
        return 1, f"FAIL: Manifest.md did not parse: {e}"

    # Phase 6 — Root.lean and Defs.lean are OPTIONAL, user-pinned inputs:
    #   Root present  = must-prove-this-exact-statement-to-exit (a HARD,
    #                   machine-checked Ingest prerequisite). The canonical
    #                   statement lives in the Lean signature so type
    #                   errors / vocab bugs surface at init time instead
    #                   of after dispatching dozens of sub-goals against a
    #                   malformed spec (Polar 2026-05-23 lost ~50 goals).
    #   Defs present  = author-vouched anchor vocabulary (pre-vouched in
    #                   review; the framework must cite, not re-derive).
    #   Neither       = pure-NL mode: the Strategist derives everything
    #                   from the Manifest (Forward defs/claims +
    #                   MarkDeliverable), and the exit is its Ingest
    #                   judgment alone.
    defs_lean = pdir / "Defs.lean"
    root_lean = pdir / "Root.lean"
    present = [p for p in (defs_lean, root_lean) if p.exists()]

    # Type-check gate: every present file must build cleanly before the
    # framework wires up the problem in the DB. --force bypasses the
    # gate for transitional situations only (e.g. operator knows the
    # error is in an unrelated downstream module).
    if not force:
        from ..pipeline._lake import lake_build
        for path in present:
            ok, bmsg = lake_build(workspace, path)
            if not ok:
                rel = path.relative_to(workspace).as_posix()
                return 1, f"FAIL: {rel} did not type-check.\n{bmsg}"

    statement: str | None = None
    if root_lean.exists():
        # Extract `goals.statement` from Root.lean's theorem signature.
        statement = _extract_root_statement(
            root_lean.read_text(encoding="utf-8"))
        if statement is None:
            return 1, (
                f"FAIL: could not parse `theorem main : <stmt> := by sorry`\n"
                f"  from {root_lean.relative_to(workspace).as_posix()}.\n"
                f"  Use the canonical shape so init can extract the "
                f"statement\n"
                f"  for the goals.statement DB column.")

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
        # catch it at the source. (Cross-problem `Problems.<other>.` refs
        # are out of scope: 0 exist today, and a real one should be a
        # Library citation, not a raw Problems reference.)
        self_prefix = f"Problems.{problem}."
        if self_prefix in statement:
            return 1, (
                f"FAIL: root statement hard-codes its own namespace "
                f"`{self_prefix}`.\n"
                f"  Drop the prefix and use the bare name — the theorem is "
                f"already inside\n"
                f"  `namespace Problems.{problem}` with `import "
                f"Problems.{problem}.Defs`,\n"
                f"  so e.g. `{self_prefix}Foo` should be written `Foo`.\n"
                f"  (Keeps the statement Library-portable for the "
                f"Librarian's re-derivation gate.)")

    proofs_dir = pdir / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)

    conn = db.connect(workspace / "asterism.db")
    db.init_schema(conn)

    existing = conn.execute(
        "SELECT 1 FROM problems WHERE name = ?", (problem,)
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
            (problem, str(mfst_path.relative_to(workspace).as_posix()), db.now()),
        )
    # v35 — every problem has a top discussion group, its human-facing
    # one. Unconditional (not gated on `existing`): a problem initialised
    # before v35 and re-inited afterwards must acquire one too, and a
    # problem without a group has no seat for its Strategist at all.
    from ..state import groups as _groups
    _groups.ensure_top_group(conn, problem)

    if statement is None:
        # Pure-NL: no root goal row. The problem starts with zero goals —
        # structurally stalled — so the T4 stall wake bootstraps the
        # Strategist's first Inject from the Manifest alone.
        msgs.append(
            f"OK: init {problem} (pure-NL — no Root.lean; the Strategist "
            f"bootstraps from the Manifest)")
    else:
        existing_goal = conn.execute(
            "SELECT id FROM goals WHERE problem = ? AND slug = 'main'",
            (problem,),
        ).fetchone()
        if existing_goal is None:
            rel_root = (pdir / "Root.lean").relative_to(workspace).as_posix()
            # Phase 5: root starts as `frozen` — invisible to BFS until
            # the Strategist Injects Backward on it (auto-reopen). Phase 6
            # retired the first_launch trigger; the initial wake now comes
            # from the T4 stall (a fresh problem has nothing dispatchable).
            gid = db.insert_goal(
                conn, problem=problem, slug="main",
                lean_path=rel_root, statement=statement,
                origin="root", depth=0,
                status="frozen",
            )
            msgs.append(f"OK: init {problem}, root goal id={gid}")
        else:
            msgs.append(f"OK: {problem} already initialized "
                        f"(goal id={existing_goal['id']})")
    conn.commit()
    # Paper v2 (D13): migrate the legacy Manifest `paper:` pointer into
    # the problem_papers binding table (idempotent; scholar/user
    # bindings accrue alongside).
    if getattr(mfst, "paper", ""):
        db.bind_paper(conn, problem=problem, paper_id=mfst.paper,
                      origin="manifest")
    # Frontmatter dissolve: seed problem_settings from the authored
    # Manifest (idempotent — keys already in the DB are never
    # clobbered; from here on the DB is the settings SoT and the
    # frontmatter lines are legacy fallback).
    from ..state import settings as _settings
    _settings.migrate_from_manifest(conn, problem, mfst)
    # Initial TREE.md so readers see structure right after init.
    tree.write(conn, workspace, problem)
    # Initial BRIEF.md — framework-rendered cross-spawn stable context
    # (sandbox / forbidden lemmas / mathlib hints / library / strategic
    # notes). Refreshed at daemon startup if Manifest changes.
    brief.write(workspace, mfst, conn=conn)
    # No LESSONS.md seed: Phase 12 Model B made the KB the lessons SoT —
    # reflection writes `kb_entries`, Context reads `kb.query`; the old flat
    # LESSONS.md mirror (and its Edit-anchor seed) is retired.
    return 0, "\n".join(msgs)


def _hard_exit_after_fatal(rc: int) -> None:
    """ZOMBIE-LOCK seam: after a dispatcher FATAL, `os._exit` is the only
    way to actually die — the pool's non-daemon worker threads (blocked on
    claude subprocesses) otherwise keep the process alive holding the
    daemon.pid lock, with no main loop left to cascade their results
    (sphere daemon #3, 2026-07-05). Module-level so tests can stub it and
    observe the re-raise instead of losing the test runner."""
    os._exit(rc)


def cmd_run(args: argparse.Namespace) -> int:
    workspace = Path.cwd()
    from . import config as _cfg
    _cfg_err = _cfg.load_error(workspace)
    if _cfg_err:
        print(f"[cli] REFUSING to run: config unparseable — running on "
              f"defaults would evaporate the run's settings: {_cfg_err}",
              flush=True)
        return 1
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
    # SSE tail pointer: the web UI follows daemon-current.txt. EVERY run
    # path must update it — when only daemon_start (the UI button) did,
    # a terminal-started run left the web log tail silently replaying
    # the previous run's file.
    try:
        (workspace / LOG_DIR / "daemon-current.txt").write_text(
            str(log_path), encoding="utf-8")
    except OSError:
        pass
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    sys.stdout = _Tee(orig_stdout, log_file)
    sys.stderr = _Tee(orig_stderr, log_file)
    # The seat table goes in FIRST, before any dispatch line: what the
    # filename used to claim (and got wrong) now lives where it can be
    # true — one line per pipeline, with the model it actually runs.
    print(seat_banner(), flush=True)
    # Provider drift guard (background, non-fatal): does each seated
    # CLI still answer the way its capability entry says it does? Every
    # quota / misconfig detector we own is a substring match against
    # vendor prose, so a wording change at the SAME version is silent
    # until a run gets nowhere. Off the startup path because the probes
    # are CLI cold starts and nothing about dispatch waits on them.
    from ..llm import drift_guard as _drift_guard
    _drift_guard.start_background(workspace)
    try:
        rc = dispatcher.run(
            workspace,
            once=getattr(args, "once", False),
            scope=getattr(args, "scope", None),
        )
        _write_exit_summary(workspace, rc=rc, error=None,
                            scope=getattr(args, "scope", None))
        return rc
    except Exception as exc:
        _write_exit_summary(
            workspace, rc=2,
            error=f"{type(exc).__name__}: {exc}"[:400],
            scope=getattr(args, "scope", None))
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
        # ZOMBIE-LOCK guard (`_hard_exit_after_fatal` seam below;
        # sphere daemon #3, 2026-07-05): re-raising kills
        # only the MAIN thread — the pool's non-daemon worker threads (each
        # blocked on a claude subprocess for up to ~16min) keep the PROCESS
        # alive, still holding the daemon.pid lock and blocking every
        # restart, while no main loop exists to cascade their results. Kill
        # the registered in-flight subprocesses (same machinery as the
        # breaker exits) and hard-exit: the work is unrecoverable either
        # way, and the v17 lease sweep + startup recovery reclaim it.
        try:
            from ..llm import claude_cli as _ccli
            n = _ccli.request_shutdown()
            if n:
                print(f"[dispatcher] killed {n} in-flight claude "
                      f"subprocess(es) before FATAL exit", flush=True)
        except Exception:  # noqa: BLE001 — never mask the original crash
            pass
        sys.stdout, sys.stderr = orig_stdout, orig_stderr
        try:
            log_file.close()
        except OSError:
            pass
        _hard_exit_after_fatal(2)   # production: never returns
        raise                       # tests stub the seam → crash propagates
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
            from ..state.thresholds import SHELVE_THRESHOLD as _ST
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
    Returns True on success, False on persistent failure. Body lives in
    core/fsutil (shared with the dispatcher's status-file unlinks)."""
    return fsutil.unlink_tolerant(path, retries=retries,
                                  delay_sec=backoff_s)


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


#: Everything `proofs/` may hold that belongs to a RUN rather than to the
#: problem. One list, because the sweeper and the "did we forget to sweep"
#: verifier both read it: they used to carry separate copies of the same
#: tuple, so the check shared the sweeper's blind spot and could never
#: report what the sweeper missed. It missed `patch.lean` — a Backward
#: worker's sandbox output whose home is the attempts dir; one that landed
#: here on 2026-07-14 outlived the SLC reset three weeks later, still
#: importing four `L_*` modules the same reset had deleted.
PROOFS_SWEEP_PATTERNS = (
    "L_*.lean", "_strategy_*.lean",          # the problem's own bricks
    "patch.lean", "new_*.lean",              # worker sandbox outputs
    "*.backup", "*.verify_backup", "*.verify_backup_s*",
    "*.lean.tmp", "*.lean.tmp_s*",           # verify staging, sid-keyed
)


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
    n_goals, n_strats = wipe_problem_rows(conn, problem)
    conn.commit()
    return _reset_problem_files(workspace, pdir, problem, n_goals, n_strats)


def wipe_problem_rows(conn, problem: str) -> "tuple[int, int]":
    """Delete EVERY DB row keyed to one problem, in FK-safe order — the
    shared row-wipe under both `asterism reset` and problem deletion
    (rule 10: files and DB move together, so both callers pair this
    with their own filesystem action). Caller commits.

    Problem-keyed FK children, cleared FIRST (unconditional). Every table with
    a `problem → problems(name)` FK blocks the `DELETE FROM problems` below if
    it still has rows; `library_decls` also has a `source_goal_id → goals.id`
    FK that blocks the goals DELETE. The FK children of `problems(name)` are:
    goals + strategist_decisions (handled below by gid/problem) and these two:
      - `library_decls`: a (partially) library-ized problem's classified decls.
      - `kb_entries`: lessons/antipatterns (KB-as-SoT — the old flat LESSONS.md
        sweep's successor; reflection writes a row per global lesson).
    Both observed 2026-06-28: derham_dd_zero reset crashed `FOREIGN KEY
    constraint failed` at DELETE FROM problems — first on library_decls (2
    classified), then on a kb_entries global lesson the run wrote.
    """
    conn.execute("DELETE FROM library_decls WHERE problem = ?", (problem,))
    conn.execute("DELETE FROM kb_entries WHERE problem = ?", (problem,))
    # v18: the bridge done-marker lives on the problems row — clear it with
    # the library_decls rows, or selfstart reads a bridged problem with zero
    # placed decls (the stale-marker FAIL library-verify flags). Retires the
    # manual `_drop_index_section` step from the reset recipe (STATUS rule 2).
    db.clear_library_bridged(conn, problem)

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
    # Catch-all queue sweep BY PROBLEM: the goal/strategy-targeted
    # passes above miss Problem-targeted rows (a Forward Inject queues
    # as target_kind='Problem' carrying a decision_id FK), and a
    # surviving one blocks the strategist_decisions DELETE below —
    # 2026-07-19: a force-stopped run left 2 pending Forward rows and
    # the reset died on the FK.
    conn.execute("DELETE FROM queue WHERE problem = ?", (problem,))
    conn.execute(
        "DELETE FROM strategist_decisions WHERE problem = ?", (problem,),
    )
    # Problem-keyed satellite tables (all REFERENCE problems(name), so
    # they must go before the problems row or the FK blocks the reset —
    # problem_papers had this latent gap since v23, user_file_history
    # since v28 (the actual b6 run-2 reset blocker, 2026-07-18),
    # kb_entries' problem-scoped lessons likewise, programme_revisions
    # since v30. Deliberately NOT wiped: library_decls — a bridged
    # problem must be un-harvested first, and its FK failing here is
    # the (crude) backstop for that rule.
    conn.execute("DELETE FROM problem_settings WHERE problem = ?",
                 (problem,))
    conn.execute("DELETE FROM problem_papers WHERE problem = ?",
                 (problem,))
    conn.execute("DELETE FROM user_file_history WHERE problem = ?",
                 (problem,))
    conn.execute("DELETE FROM kb_entries WHERE problem = ?",
                 (problem,))
    conn.execute("DELETE FROM programme_revisions WHERE problem = ?",
                 (problem,))
    # Discussion groups (v35). Order-independent by construction: the
    # self-FK cascades to descendants and the two mutual references with
    # strategist_decisions are both ON DELETE SET NULL — this table and
    # that one point at each other, so no delete order is right for both.
    conn.execute("DELETE FROM groups WHERE problem = ?", (problem,))
    conn.execute("DELETE FROM problems WHERE name = ?", (problem,))
    return len(gids), len(sids)


def _reset_problem_files(workspace: Path, pdir: Path, problem: str,
                         n_goals: int, n_strats: int) -> int:
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
        for pattern in PROOFS_SWEEP_PATTERNS:
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
    #   - PROGRAMME.md: rendered from programme_revisions (wiped above);
    #     the file carries the run's full route/thesis — left behind it
    #     would hand a rerun the prior run's winning worldview (leak
    #     audit for the model-comparison rerun, 2026-07-19)
    #   - _plan.md: strategists sometimes write the plan note at the
    #     problem root instead of .drafts/ (a5 run did); same leak class
    #     as PROGRAMME.md
    # BRIEF.md is intentionally NOT swept — it's auto-regenerated at
    # daemon startup from Manifest+Library.
    for name in ("TREE.md", "LESSONS.md", "Root.lean.backup",
                 "PROGRAMME.md", "_plan.md"):
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

    # Drop .presearch/ (per-goal candidate-lemma cache, keyed by goal id).
    # Same clean-baseline rationale as .drafts — plus a real hazard the
    # drafts don't have: after a reset that recreates the DB, goal ids
    # restart, and a surviving `.presearch/g<id>.md` from the old world is
    # silently served as the pre-search cache for an UNRELATED new goal
    # with the same id (stale candidate lemmas injected into its Context).
    presearch_dir = pdir / ".presearch"
    if presearch_dir.exists():
        if not _robust_rmtree(presearch_dir):
            failed_files.append(".presearch/")

    # Drop .groups/ (per-sub-group `PROGRAMME.md`, keyed by group id).
    # The top group's programme is the problem-root PROGRAMME.md swept
    # above; sub-groups project into `.groups/<id>/`, so sweeping only the
    # root was half a fix — task #167, where a rerun's revision 2 cited
    # `.groups/369` from the run before it. `DELETE FROM groups` clears
    # the DB side, which makes it the `.presearch` hazard exactly: ids are
    # re-issued after a reset, and a surviving directory becomes an
    # UNRELATED new group's research programme — the one file whose whole
    # job is to carry a worldview forward.
    groups_dir = pdir / ".groups"
    if groups_dir.exists():
        if not _robust_rmtree(groups_dir):
            failed_files.append(".groups/")

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
        for pattern in PROOFS_SWEEP_PATTERNS:
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
    print(f"  DB rows: {n_goals} goals, {n_strats} strategies cleared")
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

    # Antigravity CLI (`agy`) — the subscription-priced path to Gemini
    # models since Google cut the Gemini CLI's individual tiers off
    # (2026-06-18). Resolver probes the installer location first: the
    # PowerShell installer edits the USER PATH, which a daemon started
    # before the install never sees.
    from ..llm import antigravity_cli as _agy
    agy_exe = _agy.resolve_agy_executable()
    if agy_exe:
        try:
            r = subprocess.run(
                [agy_exe, "--version"],
                capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
            )
            v = (r.stdout or "").strip().splitlines()[0] if r.stdout else "?"
            line("OK", f"agy     {v}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            line("FAIL", f"agy --version timed out or errored: {exc}")
        # The permission file is what makes the write fence real; without
        # it every tool falls to headless auto-deny and a spawn returns
        # SUCCESS having written nothing (see antigravity_cli.py).
        perms = _agy.permissions_path()
        if perms.is_file():
            line("OK", f"agy permissions: {perms}")
            # The closed shape (2026-07-30): capability comes from OUR
            # MCP server and nothing else. `command(*)` is what let an
            # agent-authored `python -c` loop pin a wake for 32 minutes;
            # `read_url` ungated is a route to the answer for a problem
            # whose solution is on the public web.
            try:
                _p = json.loads(perms.read_text(encoding="utf-8"))
                _al = set(_p.get("permissions", {}).get("allow") or [])
                _dn = set(_p.get("permissions", {}).get("deny") or [])
            except Exception:  # noqa: BLE001
                _al = _dn = set()
            for tok, where, why in (
                ("mcp(*)", _al, "the framework's tools are unreachable"),
                ("command(*)", _dn, "arbitrary shell is open"),
                ("read_url(*)", _dn, "outbound fetch is open"),
            ):
                if tok not in where:
                    line("WARN", f"agy permissions: {tok} not in "
                                 f"{'allow' if where is _al else 'deny'} — "
                                 f"{why}")
            if "command(*)" in _al:
                line("WARN", "agy permissions: command(*) is ALLOWED — "
                             "any shell command, hence any write and any "
                             "unbounded computation")
        else:
            line("WARN", f"agy permissions file missing ({perms}) — every "
                         f"tool call will be auto-denied in headless mode")
        mcfg = _agy.mcp_config_path()
        try:
            _srv = json.loads(mcfg.read_text(encoding="utf-8") or "{}")
            _has = "asterism_tools" in (_srv.get("mcpServers") or {})
        except Exception:  # noqa: BLE001
            _has = False
        if _has:
            line("OK", f"agy MCP tools registered: {mcfg}")
        else:
            line("WARN", f"agy MCP tools not registered in {mcfg} — the "
                         f"next agy spawn re-writes it (ensure_mcp_config)")
        # Which ACCOUNT serves the run is decided silently (§2b): this
        # file outranks the Antigravity IDE session, so its presence can
        # quietly move the run onto a different subscription's quota.
        legacy = _agy.legacy_oauth_creds_path()
        if legacy.is_file():
            line("WARN", f"{legacy} exists — agy prefers it over the "
                         f"Antigravity IDE session, so THIS file's account "
                         f"pays for the run; rename it away to fall back to "
                         f"the IDE login")
        else:
            line("OK", "agy identity: Antigravity IDE session (no "
                       "oauth_creds.json overriding it)")
    else:
        line("WARN", "agy CLI not on PATH (Antigravity provider "
                     "unavailable)")

    # Provider capability declarations vs. what is actually installed.
    # The daemon runs this in the background at start; doctor runs it in
    # the foreground because doctor IS the place you look when a
    # detector has gone quiet. Warnings only — a version bump or a
    # reworded error never blocks a run.
    print("\n=== Provider capabilities ===")
    from ..llm import capabilities as _caps
    from ..llm import drift_guard as _drift
    for _prov in sorted(_caps.CAPABILITIES):
        _c = _caps.CAPABILITIES[_prov]
        line("OK", f"{_prov}: rc={_c.rc_contract} "
                   f"usage_endpoint={_c.usage_endpoint} "
                   f"stream_events={_c.stream_events} "
                   f"resume={_c.session_resume} "
                   f"enforcement={_c.enforcement_strength} "
                   f"tested@{_c.tested_version or '—'}")
    try:
        for _w in _drift.check(workspace):
            line("WARN", _w)
    except Exception as exc:  # noqa: BLE001 — a guard never fails doctor
        line("WARN", f"provider drift guard errored: {exc}")

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
                     f"(see Tooling/core/config.py for keys)")
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


def _library_consistency_findings(conn, workspace: Path
                                  ) -> "list[tuple[str, str]]":
    """DB <-> disk consistency over the *placed* decl set (v18: the DB IS
    the index — the former INDEX.md three-way checks I3/I4 are structurally
    impossible and retired).

    "Placed" = `library_decls.lifecycle IN ('migrated','cleaned')` — exactly
    the harvested set. 'cited'/'dropped'/'classified' decls are NOT placed
    (no file contribution), so they never participate. Mirrors the
    problem-side recovery orphan-sweep, but for `Library/`.

    Printer-free on purpose: returns `[(status, message), ...]` with status in
    {OK, WARN, FAIL} so the caller prints/exits and tests assert on findings.
    Severity rationale:
      - DB row -> missing file / orphan disk file: hard breaks (a citer is
        misled, or a file nothing owns lingers) -> FAIL.
      - bridged marker set but no placed decls: stale marker -> FAIL.
      - placed decls but not yet bridged: legit mid-flight -> WARN."""
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

    # I3 — bridged marker <-> placed-set agreement (was: INDEX section vs
    # DB; the marker is now `problems.library_bridged_at`).
    bridged = {str(r["name"]) for r in conn.execute(
        "SELECT name FROM problems WHERE library_bridged_at IS NOT NULL")}
    for prob in sorted(bridged | set(db_by_problem)):
        if prob in bridged and prob not in db_by_problem:
            out.append(("FAIL", f"{prob}: bridge marker set but no placed "
                                f"DB decls (stale marker)"))
        elif prob not in bridged:
            out.append(("WARN", f"{prob}: {len(db_by_problem[prob])} placed "
                                f"decl(s) but not bridged yet (mid-flight?)"))
        else:
            out.append(("OK", f"{prob}: bridged, {len(db_by_problem[prob])} "
                              f"placed decl(s)"))

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

      (B) DB <-> disk consistency over the placed decl set — orphan
          files, DB rows pointing at missing files, stale bridge markers.
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

    print("\n=== Consistency (DB <-> disk) ===")
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
    """anchor+claim review surface (docs/internal/archive/anchor_claim_design.md).

    For every goal the Strategist marked `is_deliverable=1` (optionally
    scoped by `problem`), compute its kernel anchor closure and present
    the anchors (defs the human must vouch for) + claims (lemmas the
    closure rests on), partitioned. Reject an entry with
    `asterism reject <decl>` (Phase 3).

    Read-only. Needs the gateway (reused if already warm; else warmed —
    slow on a cold Mathlib cache). Exit 0 always (a review, not a gate);
    deliverables whose closure could not be computed print a WARN."""
    from ..quality import review as review_mod

    workspace = Path.cwd()
    conn = db.connect()
    db.init_schema(conn)
    scope = getattr(args, "problem", None)
    fresh = bool(getattr(args, "fresh", False))
    # Snapshot-first (charter §5-4): the Ingest commit stored the closure
    # while the gateway was warm; reading it costs nothing. --fresh (or a
    # problem never snapshotted) recomputes live and refreshes the store.
    data = None
    snap_note = ""
    if scope and not fresh:
        snap = review_mod.load_review_snapshot(conn, scope)
        if snap is not None:
            data, at = snap
            snap_note = (f"(snapshot from {at[:19]} — "
                         f"`--fresh` recomputes)")
    if data is None:
        data = review_mod.review_data(conn, workspace, problem=scope)
        if scope and data["deliverables"]:
            db.set_review_snapshot(
                conn, scope, json.dumps(data, ensure_ascii=False))

    if not data["deliverables"]:
        conn.close()
        where = f" for '{scope}'" if scope else ""
        print(f"no deliverables{where} (Strategist marks them via "
              f"is_deliverable; none set yet)")
        return 0
    conn.close()

    def render(items: list[dict], head: str) -> None:
        if not items:
            return
        print(f"    {head}")
        for c in sorted(items, key=lambda x: x["name"]):
            mod = c.get("module") or "<local>"
            print(f"      - {c['name']}   ({mod})")

    print(f"\n=== anchor+claim review: {scope or 'all problems'} "
          f"{snap_note}===")
    for d in data["deliverables"]:
        if not d["ok"]:
            print(f"\n▸ {d['fq']}  [WARN] closure unavailable: {d['error']}")
            continue
        print(f"\n▸ {d['fq']}  [{d['kind']}]   "
              f"(module {d['module'] or '<local>'})")
        if d["paper"]:
            print(f"    {d['paper']}")
        if not d["anchors"] and not d["claims"]:
            print("    (no pending anchors — statement rests entirely on "
                  "Mathlib ∪ Library)")
        render(d["anchors"], "anchors (defs you must vouch for):")
        render(d["claims"], "claims (lemmas the closure rests on):")
        if d["folded"]:
            print(f"      (+{d['folded']} compiler-generated companions "
                  f"folded into their parent inductive)")

    print(f"\n=== {len(data['deliverables'])} deliverable(s), "
          f"{data['union_count']} distinct pending anchor(s)/claim(s) ===")
    return 0


# review_data / _deliverable_paper_line moved to Tooling/quality/review.py
# (charter §5-4): the Strategist's Ingest-commit snapshot hook needs them,
# and pipeline code must not import the CLI entrypoint layer.


def _write_exit_summary(workspace: Path, *, rc: "int | None",
                        error: "str | None",
                        scope: "str | None" = None) -> None:
    """Record how the last run ended (read by `daemon_status` when
    idle) — a crashed run must not be indistinguishable from a finished
    one (both used to read 'Idle'). `scope` pins the ending to the
    problem it happened on, so its cockpit can surface the crash."""
    try:
        p = workspace / LOG_DIR / "daemon-exit.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(
            {"at": db.now(), "rc": rc, "error": error, "scope": scope}),
            encoding="utf-8")
    except OSError:
        pass


def _read_exit_summary(workspace: Path) -> "dict | None":
    try:
        raw = (workspace / LOG_DIR / "daemon-exit.txt").read_text(
            encoding="utf-8")
        d = json.loads(raw)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


# Serializes check-then-spawn within one process (the serve API handles
# two Run clicks on two threads); the cross-process guard is the
# daemon-starting marker + the child's singleton lock.
_daemon_start_lock = threading.Lock()


def _daemon_live_pid(workspace: Path) -> "int | None":
    """Singleton-lock liveness: the daemon's pid iff the lock file names
    a live daemon instance (pid + start-time identity, the same
    reuse-proof check the lock itself uses)."""
    from . import dispatcher as _disp
    pid_file = workspace / ".asterism" / "daemon.pid"
    try:
        lines = pid_file.read_text(encoding="utf-8").splitlines()
        pid = int(lines[0].strip())
        start = float(lines[1].strip()) if len(lines) > 1 else None
    except (OSError, ValueError, IndexError):
        return None
    return pid if _disp._lock_held_by_live_daemon(pid, start) else None


def _daemon_in_flight(workspace: Path) -> int:
    path = workspace / "asterism.db"
    if not path.exists():
        return 0
    try:
        # Read-only on purpose: db.connect() CREATES a missing file (a
        # write), and this runs from the serve API's status poll too.
        conn = db.connect_readonly(path)
        n = conn.execute(
            "SELECT count(*) FROM queue WHERE owner_pid IS NOT NULL"
        ).fetchone()[0]
        conn.close()
        return int(n)
    except Exception:  # noqa: BLE001 — status must not crash
        return -1


def daemon_status(workspace: Path) -> dict:
    """Daemon lifecycle status dict (shared by `asterism daemon status`
    and the serve API — one implementation, two surfaces)."""
    import time as _time
    from . import dispatcher as _disp
    pid = _daemon_live_pid(workspace)
    # Boot window: daemon_start has returned but the child hasn't claimed
    # the singleton lock yet (heavy imports — seconds). The start side
    # already covers this gap with the anti-double-spawn marker; the
    # STATUS side must read the same marker or it reports "idle" and the
    # UI's Run button flashes back mid-start (owner, 2026-07-12). The
    # child consumes the marker right after claiming the lock, so
    # starting → running is seamless; a crashed boot ages out at 60s
    # (the marker's own staleness rule).
    starting = False
    if pid is None:
        try:
            marker = workspace / ".asterism" / "daemon-starting.txt"
            starting = _time.time() - marker.stat().st_mtime < 60
        except OSError:
            starting = False
    scope: str | None = None
    started_at: str | None = None
    if pid is not None or starting:
        # written by daemon_start; "" = workspace-wide (--all-problems)
        scope_file = workspace / ".asterism" / "logs" / "daemon-scope.txt"
        try:
            scope = scope_file.read_text(encoding="utf-8").strip() or None
        except OSError:
            scope = None
    if pid is not None:
        # pid-file line 2 is the daemon's process start time (the same
        # identity the singleton lock checks) — that IS this run's start.
        try:
            lines = (workspace / ".asterism" / "daemon.pid").read_text(
                encoding="utf-8").splitlines()
            started_at = datetime.fromtimestamp(
                float(lines[1].strip()), timezone.utc).isoformat()
        except (OSError, ValueError, IndexError):
            started_at = None
    code_stale = False
    if pid is not None:
        # the daemon writes its code fingerprint at boot; a mismatch
        # against the CURRENT tree means it runs old code. Transient by
        # design — the daemon's own drift watchdog drains and hands off
        # — but the status must say so while it lasts.
        try:
            born_fp = (workspace / ".asterism" / "logs" /
                       "daemon-fp.txt").read_text(encoding="utf-8").strip()
            if born_fp:
                from ..lsp.lifecycle import code_fingerprint
                code_stale = born_fp != code_fingerprint()
        except OSError:
            code_stale = False
    return {
        "running": pid is not None,
        # the boot window between daemon_start and the child's lock claim
        "starting": starting,
        "pid": pid,
        "scope": scope,
        "started_at": started_at,
        "code_stale": code_stale,
        # a stop-file left behind by a dead daemon is residue, not a
        # state — "stopping" is only meaningful while something runs
        "stopping": pid is not None
        and _disp.stop_file_path(workspace).exists(),
        "in_flight_leases": _daemon_in_flight(workspace),
        # gateway phase ('warming'/'ready'/None): the first minutes of
        # a cold run are Lean warm-up — without this the user stares
        # at dead air (Test.Test3 run, 2026-07-07)
        "gateway": _gateway_phase_safe(workspace),
        # how the LAST run ended ({at, rc, error, scope}) — only
        # meaningful while idle; tells "finished" from "crashed", and a
        # BOOTING run's page must not resurface the previous ending
        "last_exit": None if (pid is not None or starting)
        else _read_exit_summary(workspace),
    }


def _gateway_phase_safe(workspace: Path) -> "str | None":
    try:
        from ..lsp.lifecycle import gateway_phase
        return gateway_phase(workspace)
    except Exception:  # noqa: BLE001 — status must not crash
        return None


def daemon_start(workspace: Path, *, scope: "str | None" = None,
                 once: bool = False,
                 wait_lock_sec: float = 0.0) -> "tuple[int, str]":
    """Detached daemon start. Returns (exit_code, message). Refuses (1)
    while a daemon holds the singleton lock; on success writes the
    per-run log + the daemon-current.txt pointer the SSE tail follows.

    `wait_lock_sec` > 0 retries the refusal for that long — the code-
    drift HANDOFF relay uses it: the dying daemon spawns this waiter
    BEFORE releasing its own lock, and the waiter's start lands the
    moment the lock frees."""
    import subprocess
    import time as _time
    from . import config as _cfg
    from . import dispatcher as _disp
    # B4 (2026-07-24): a present-but-unparseable config must refuse the
    # start — silently running on defaults evaporates the run's settings.
    _cfg_err = _cfg.load_error(workspace)
    if _cfg_err:
        return 1, (f"config unparseable — refusing to start on defaults: "
                   f"{_cfg_err}. Fix Asterism.yaml (or the python env) "
                   "and retry.")
    # #158: a scope matching no registered problem can never dispatch —
    # the daemon would boot and idle forever, indistinguishable from
    # health (08-04 SLC: `reset` deletes the problems row; two restarts
    # idled ~20min before the missing `init` was noticed). Refuse here,
    # in the caller's face; dispatcher.run re-checks for direct `run`
    # invocations and the code-drift handoff successor.
    if scope:
        _mismatch = _disp.scope_mismatch_reason(workspace, scope)
        if _mismatch:
            return 1, _mismatch
    deadline = _time.time() + wait_lock_sec
    while True:
        refusal: "str | None" = None
        with _daemon_start_lock:
            pid = _daemon_live_pid(workspace)
            if pid is not None:
                refusal = (f"REFUSED: a daemon is already running (pid {pid})"
                           f" — one daemon per workspace (singleton lock)")
            else:
                # Anti-double-spawn window: the child takes seconds to boot
                # and claim the singleton lock; two near-simultaneous starts
                # both passed the check above and both spawned (the loser
                # died silently AFTER this call returned "started", and
                # last-writer scope made the UI lie about what runs). The
                # marker covers the boot gap; the child consumes it once
                # the lock is settled.
                marker = workspace / ".asterism" / "daemon-starting.txt"
                try:
                    if _time.time() - marker.stat().st_mtime < 60:
                        refusal = ("REFUSED: a daemon is already starting "
                                   "(another Run landed moments ago) — give "
                                   "it a few seconds, then check status")
                except OSError:
                    pass
                if refusal is None:
                    # Tolerant unlinks: the serve status poll reads these
                    # files every ~2s; a collision raised WinError 32 and
                    # killed the drift-handoff waiter (2026-07-13 21:01,
                    # convicted 07-14 via handoff-waiter.log).
                    fsutil.unlink_tolerant(_disp.stop_file_path(workspace))
                    logs = workspace / ".asterism" / "logs"
                    logs.mkdir(parents=True, exist_ok=True)
                    marker.write_text(db.now(), encoding="utf-8")
                    # last run's exit summary belongs to the last run — a
                    # force-killed run writes none, and a stale one must not
                    # be reported as this run's ending
                    fsutil.unlink_tolerant(logs / "daemon-exit.txt")
        if refusal is None:
            break
        if _time.time() >= deadline:
            return 1, refusal
        _time.sleep(1.0)
    log_path = logs / f"daemon_{_utc_log_stamp()}.log"
    argv = [sys.executable, "-m", "Tooling.core.cli", "run"]
    if once:
        argv.append("--once")
    if scope:
        argv += ["--scope", scope]
    else:
        argv.append("--all-problems")
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    daemon_pid: "int | str" = "?"
    if os.name == "nt":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        base_flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        # The daemon must NOT be the caller's child: taskkill /T on the
        # serve process (or any UI host) walks the LIVE parent-child
        # chain and would reap the daemon and every in-flight prover
        # with it (2026-07-10 incident — a serve restart killed the
        # putnam marathon). A relay spawns the daemon and exits at
        # once, so the daemon is reparented and the chain is broken.
        # The daemon still binds ITSELF to its own kill-on-close Job
        # Object at boot (dispatcher.run) — orphan-prover protection is
        # untouched. The relay also breaks away from the CALLER's job
        # when that job permits it (a handoff relay spawned by a dying
        # daemon must escape ITS kill-on-close job or die with it).
        from . import process_group
        relay_src = (
            "import subprocess, sys\n"
            "flags = 0x00000008 | 0x00000200\n"
            "log = open(sys.argv[2], 'ab')\n"
            "p = subprocess.Popen(sys.argv[3:], cwd=sys.argv[1],\n"
            "                     stdout=log, stderr=subprocess.STDOUT,\n"
            "                     stdin=subprocess.DEVNULL,\n"
            "                     creationflags=flags)\n"
            "print(p.pid, flush=True)\n"
        )
        relay = subprocess.Popen(
            [sys.executable, "-c", relay_src, str(workspace),
             str(log_path), *argv],
            cwd=str(workspace), stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
            creationflags=base_flags | process_group.breakaway_creationflags(),
            env=env)
        try:
            out, _ = relay.communicate(timeout=30)
            daemon_pid = int(out.strip())
        except (ValueError, subprocess.TimeoutExpired):
            daemon_pid = "?"  # relay hiccup — the singleton lock is truth
    else:
        # POSIX has no tree-kill footgun (killing serve never reaps
        # children) — the direct spawn stays.
        with open(log_path, "ab") as logf:
            proc = subprocess.Popen(
                argv, cwd=str(workspace), stdout=logf,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                start_new_session=True, env=env)
        daemon_pid = proc.pid
    # SSE tail pointer (charter appendix): per-run log filenames need
    # a stable "latest log" resolution point.
    (logs / "daemon-current.txt").write_text(
        str(log_path), encoding="utf-8")
    # scope pointer: lets status (and the UI's per-problem Run controls)
    # answer "what is the engine working on?"
    (logs / "daemon-scope.txt").write_text(scope or "", encoding="utf-8")
    return 0, f"started daemon pid {daemon_pid}; log: {log_path}"


def daemon_stop(workspace: Path, *, force: bool = False) -> "tuple[int, str]":
    """Graceful stop by default (daemon.stop file: the tick loop stops
    spawning, drains in-flight workers, exits cleanly). force=True is the
    explicit hard-kill override; the message carries the in-flight count
    being abandoned (lease sweep + startup recovery reclaim it)."""
    from . import dispatcher as _disp
    stop_file = _disp.stop_file_path(workspace)
    pid = _daemon_live_pid(workspace)
    if pid is None:
        fsutil.unlink_tolerant(stop_file)
        return 0, "no daemon running"
    if force:
        n = _daemon_in_flight(workspace)
        try:
            import psutil
            p = psutil.Process(pid)
            p.terminate()
            try:
                p.wait(timeout=10)
            except psutil.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
        except Exception as e:  # noqa: BLE001
            return 1, f"terminate failed: {e}"
        # Post-kill hygiene — TerminateProcess skips atexit, so nothing
        # else runs: a leftover stop-file used to wedge "stopping" into
        # the status, and the dead pid's leases rendered as running
        # agents until some future daemon start happened to sweep them
        # (scope-filtered, so possibly never).
        fsutil.unlink_tolerant(stop_file)
        released = 0
        db_path = workspace / "asterism.db"
        if db_path.exists():
            try:
                import psutil as _ps

                def _alive(owner) -> bool:
                    try:
                        o = int(owner)
                    except (TypeError, ValueError):
                        return False
                    return o != pid and _ps.pid_exists(o)
                conn = db.connect(db_path)
                released = db.release_expired_leases(
                    conn, ttl_sec=float("inf"), pid_alive=_alive)
                conn.commit()
                conn.close()
            except Exception:  # noqa: BLE001 — hygiene must not fail the stop
                released = 0
        try:
            _sc = (workspace / ".asterism" / "logs" /
                   "daemon-scope.txt").read_text(
                encoding="utf-8").strip() or None
        except OSError:
            _sc = None
        _write_exit_summary(workspace, rc=None,
                            error="force-stopped by the user", scope=_sc)
        return 0, (f"force-stopped pid {pid}; released {released} of "
                   f"{n} in-flight lease(s)")
    stop_file.write_text(db.now(), encoding="utf-8")
    return 0, (f"stop requested (graceful): daemon pid {pid} will finish "
               f"in-flight work and exit; `daemon status` to watch, "
               f"`daemon stop --force` to terminate immediately")


def cmd_daemon(args) -> int:
    """Daemon lifecycle (frontend charter §5-3): detached start / graceful
    stop / status — thin CLI shell over daemon_status/start/stop (the
    serve API imports those directly)."""
    import json as _json
    from ..core import config as _config

    workspace = _config.resolve_workspace(getattr(args, "workspace", None))
    action = args.daemon_action
    if action == "status":
        print(_json.dumps(daemon_status(workspace)))
        return 0
    if action == "start":
        code, msg = daemon_start(
            workspace, scope=getattr(args, "scope", None),
            once=getattr(args, "once", False),
            wait_lock_sec=getattr(args, "wait_lock", 0.0))
        print(msg)
        return code
    if action == "stop":
        code, msg = daemon_stop(
            workspace, force=getattr(args, "force", False))
        print(msg)
        return code
    print(f"unknown daemon action {action!r}")
    return 2


def cmd_serve(args) -> int:
    """`asterism serve` — the localhost web UI (frontend charter §0
    form A). One process per workspace; reads are connect_readonly,
    writes go through the same chokepoints the CLI uses.

    chdir to the workspace before serving: the write chokepoints
    (cmd_approve_ingest etc.) open the DB via the cwd-relative default
    path, same as every terminal invocation."""
    import uvicorn
    from ..core import config as _config
    from ..serve.app import create_app

    workspace = _config.resolve_workspace(getattr(args, "workspace", None))
    os.chdir(workspace)
    host = "127.0.0.1"
    port = int(getattr(args, "port", None) or 8642)
    app = create_app(workspace, prewarm=True)
    print(f"Asterism UI: http://{host}:{port}/  (workspace: {workspace})")
    uvicorn.run(app, host=host, port=port, log_level="warning")
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
    from ..pipeline._constants import canonicalize_anchor_pending
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
        # Canonicalize internal strategy names → public goal slugs BEFORE the
        # match: a lone-`s<N>` anchor in the closure would never equal the
        # rejected goal's public `fqn`, silently dropping a true victim from
        # the cascade. Same rename the review surface applies. #71.
        pending = canonicalize_anchor_pending(
            conn, workspace, d["problem"], r.pending)
        if any(c["name"] == fqn for c in pending):
            victims.append((did, f"Problems.{d['problem']}.{d['slug']}"))
    return victims, warnings


def cmd_reject(args: argparse.Namespace) -> int:
    """anchor+claim reject (docs/internal/archive/anchor_claim_design.md §2.5).

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


def _rewake_strategist(conn, problem: str) -> None:
    """Enqueue a Strategist wake on the problem (dedup), so a paused/idle
    problem gets re-planned on the next dispatcher tick. Phase 6 —
    problem-keyed (the old root-goal key made pure-NL problems
    unwakeable)."""
    if not db.is_in_queue(conn, target_id=problem, kind="Strategist"):
        db.enqueue(conn, kind="Strategist", target_id=problem,
                   target_kind="Problem", priority=20, problem=problem)


def _claude_login_email() -> "str | None":
    """The Claude account logged in RIGHT NOW (~/.claude.json
    oauthAccount) — captured as sign-off evidence, never typed. This is
    the COMPUTE account, not the reviewer's identity (the operator
    switches accounts for quota); it rides in the record's fine print
    so an implausible signature is visibly implausible."""
    import json as _json
    try:
        data = _json.loads((Path.home() / ".claude.json").read_text(
            encoding="utf-8"))
        email = (data.get("oauthAccount") or {}).get("emailAddress")
        return str(email) if email else None
    except (OSError, ValueError):
        return None


def _effective_library_flag(conn, problem: str) -> bool:
    """The harvest decision as the librarian scheduler will see it:
    `problem_settings` row wins, Manifest.md value is the fallback,
    unreadable-anything reads False (no harvest without an explicit
    opt-in — mirrors the `library` default)."""
    from ..state import settings as _settings
    val = _settings.read(conn, problem).get("library")
    if isinstance(val, bool):
        return val
    try:
        from ..state import manifest as _manifest
        row = conn.execute(
            "SELECT manifest_path FROM problems WHERE name = ?",
            (problem,)).fetchone()
        if row is None:
            return False
        return bool(_manifest.parse(Path(row["manifest_path"])).library)
    except Exception:  # noqa: BLE001 — conservative: no silent harvest
        return False


def _signoff_record(conn, problem: str,
                    signer: "str | None") -> dict:
    """The signature written at approve: the operator's claim (name),
    the machine's observations (evidence + timestamp), and the seal
    (sha256 of the exact review snapshot the human was shown)."""
    import getpass
    import hashlib
    import socket
    snap = db.get_review_snapshot(conn, problem)
    return {
        "name": (signer or "").strip() or None,
        "at": db.now(),
        "snapshot_sha": (hashlib.sha256(
            snap[0].encode("utf-8")).hexdigest() if snap else None),
        "evidence": {
            "claude_email": _claude_login_email(),
            "os_user": getpass.getuser(),
            "host": socket.gethostname(),
        },
    }


def cmd_approve_ingest(args: argparse.Namespace) -> int:
    """anchor+claim: approve a paused ingest → harvest to Library.

    The single resume action of the sign-off gate (not a per-anchor
    checklist): clears the pause, RECORDS THE SIGNATURE (v27 — who
    signed, when, sealing exactly what was reviewed), and enqueues the
    Librarian iff the effective `library` flag says harvest (the serve
    endpoint writes the signer's Library decision through the settings
    chokepoint BEFORE calling here — signing with library:false must
    not start a harvest). Reject specific anchors/claims BEFORE
    approving via `asterism reject`."""
    conn = db.connect()
    db.init_schema(conn)
    problem = args.problem
    if not db.problem_ingest_signoff_pending(conn, problem):
        print(f"{problem!r} is not awaiting ingest sign-off "
              f"(nothing paused).")
        return 1
    db.set_ingest_signoff_pending(conn, problem, False)
    record = _signoff_record(conn, problem,
                             getattr(args, "signer", None))
    db.set_ingest_signoff(conn, problem, record)
    from ..state import transitions as _transitions
    _transitions.apply_problem_transition(
        conn, problem, "ingested", event="signoff_approved")
    signed = f" signed by {record['name']}" if record["name"] else ""
    if _effective_library_flag(conn, problem):
        db.enqueue(conn, kind="Librarian", target_id=problem,
                   target_kind="Problem", priority=0, problem=problem)
        print(f"approved ingest for {problem}{signed} — enqueued "
              f"Librarian; harvest runs on the next dispatcher tick.")
    else:
        print(f"approved ingest for {problem}{signed} — library: false, "
              f"no harvest.")
    conn.close()
    return 0


def cmd_reject_ingest(args: argparse.Namespace) -> int:
    """anchor+claim: reject a paused ingest → back to proving.

    Use when the deliverables aren't actually complete yet (no specific
    anchor/claim is wrong — the work just isn't done). Clears the pause,
    records the reason as a Strategist directive, and re-wakes the
    Strategist to keep proving. No harvest."""
    conn = db.connect()
    db.init_schema(conn)
    problem = args.problem
    reason = getattr(args, "reason", None) or "(no reason given)"
    if not db.problem_ingest_signoff_pending(conn, problem):
        print(f"{problem!r} is not awaiting ingest sign-off "
              f"(nothing paused).")
        return 1
    db.set_ingest_signoff_pending(conn, problem, False)
    # Phase 6 — rejecting the sign-off revokes the terminal judgment: the
    # problem returns to the live path (T1/T4/exit all key off the stamp).
    db.set_problem_ingested(conn, problem, ingested=False)
    # a revoked judgment must not keep wearing its seal — the next
    # approve signs the NEXT reviewed content afresh
    db.set_ingest_signoff(conn, problem, None)
    from ..state import transitions as _transitions
    _transitions.apply_problem_transition(
        conn, problem, "active", event="signoff_rejected")
    row = conn.execute(
        "SELECT strategist_directive FROM problems WHERE name = ?",
        (problem,)).fetchone()
    existing = (row["strategist_directive"] or "").strip() if row else ""
    note = (f"[user rejected ingest — not yet complete] {reason} "
            f"Keep proving toward the missing pieces before the next Ingest.")
    db.set_problem_strategist_directive(
        conn, problem, f"{note}\n\n{existing}".strip() if existing else note)
    _rewake_strategist(conn, problem)
    print(f"rejected ingest for {problem} — back to proving; the Strategist "
          f"re-plans on its next wake with your reason.")
    conn.close()
    return 0


def cmd_regress(args: argparse.Namespace) -> int:
    """Regression-manifest report (task #8): compare the tracked
    `Benchmarks/proved_manifest.jsonl` against the CURRENT workspace.
    RESET/PARTIAL lines are re-verification CANDIDATES (resets are a
    normal workflow), DRIFT = not re-verified since a toolchain bump.
    Always exits 0 — this is a report, not a gate."""
    from ..state import regress
    workspace = Path.cwd()
    conn = db.connect()
    try:
        findings = regress.report(conn, workspace)
    finally:
        conn.close()
    if not findings:
        print("regress: manifest empty — nothing recorded yet")
        return 0
    icons = {"OK": "[OK]  ", "RESET": "[RESET]", "PARTIAL": "[PART] ",
             "DRIFT": "[DRIFT]"}
    for status, msg in findings:
        print(f"{icons.get(status, status)} {msg}")
    n = sum(1 for s, _ in findings if s != "OK")
    print(f"regress: {len(findings)} recorded problem(s), "
          f"{n} re-verification candidate(s)")
    return 0


def cmd_knowledge_stats(args: argparse.Namespace) -> int:
    """Offline knowledge-layer telemetry (read-only; safe alongside a
    running daemon). See Tooling/quality/knowledge_stats.py for metric
    semantics — the presearch citation number is a drift canary, NOT
    the value metric."""
    import sqlite3 as _sq
    from ..core import config as _config
    from ..quality import knowledge_stats
    workspace = _config.resolve_workspace(getattr(args, "workspace", None))
    conn = _sq.connect(
        f"file:{(workspace / 'asterism.db').as_posix()}?mode=ro", uri=True)
    conn.row_factory = _sq.Row
    print(knowledge_stats.render(conn, workspace,
                                 problem_like=args.problem))
    return 0


def cmd_repin(args: argparse.Namespace) -> int:
    """Operator acknowledgment of a deliberate user-file edit
    (self-audit 2026-07-12 §3-3): record the CURRENT content of the
    problem's user-intent files as 'repin' baselines in
    `user_file_history`, so `root_integrity_gate` accepts the current
    bytes again. NOTE: repin acknowledges BYTES only — if the root
    STATEMENT's meaning changed, `goals.statement` is stale and the
    honest path is re-init (or sync), not repin."""
    from ..state import manifest as _mfst
    workspace = Path.cwd()
    problem = str(args.problem)
    files = ([args.file] if getattr(args, "file", None)
             else list(_mfst.USER_INTENT_FILES))
    conn = db.connect()
    try:
        if conn.execute("SELECT 1 FROM problems WHERE name = ?",
                        (problem,)).fetchone() is None:
            print(f"[repin] unknown problem {problem!r}")
            return 1
        pdir = db.problem_dir(workspace, problem)
        n = 0
        for name in files:
            path = pdir / name
            if not path.is_file():
                continue
            body = path.read_text(encoding="utf-8")
            sha = _mfst._content_sha(body)
            conn.execute(
                "INSERT INTO user_file_history"
                " (problem, file, sha, body, seen_at, source)"
                " VALUES (?, ?, ?, ?, ?, 'repin')",
                (problem, name, sha, body, db.now()))
            n += 1
            print(f"  repinned {name} (sha {sha})")
        conn.commit()
    finally:
        conn.close()
    print(f"[repin] {problem}: {n} file(s) re-baselined")
    return 0


def cmd_revive(args: argparse.Namespace) -> int:
    """Problem FSM §2.1: re-enter a REVOKED problem (post-Ingest
    un-prove quarantine) into the live path. The incident announcement
    (seal torn, Library un-harvested) already happened automatically;
    this is the operator's re-grind decision. Clears `ingested_at` so
    the liveness machinery resumes wakes/dispatch."""
    from ..state import transitions as _transitions
    conn = db.connect()
    db.init_schema(conn)
    problem = str(args.problem)
    row = conn.execute("SELECT state FROM problems WHERE name = ?",
                       (problem,)).fetchone()
    if row is None:
        print(f"[revive] unknown problem {problem!r}")
        return 1
    if str(row["state"]) != "revoked":
        print(f"[revive] {problem!r} is {row['state']!r}, not 'revoked' — "
              f"nothing to revive.")
        return 1
    db.set_problem_ingested(conn, problem, ingested=False)
    _transitions.apply_problem_transition(
        conn, problem, "active", event="operator_revived")
    print(f"[revive] {problem}: back on the live path — wakes and "
          f"dispatch resume on the next daemon tick.")
    conn.close()
    return 0


def cmd_drift_check(args: argparse.Namespace) -> int:
    """Consistency gate, two layers (run with the daemon STOPPED — a
    mid-tick snapshot can transiently trip the tree predicates):
      1. DB<->file (`proof_store.inventory`): orphan proof files, missing
         files, proved-with-sorry.
      2. Tree-level DB (`consistency.consistency_sweep`, task #11): the
         crash-window audit's predicates — interrupted-cascade leftovers
         no single-row reconciler sees (succeeded strategy under an
         unproved goal, live strategy under a terminal goal, unreachable
         alive goals, pending revivals).
    Exit 0 if consistent, 1 on any finding. `--scope` limits (LIKE)."""
    from ..state import consistency, proof_store
    workspace = Path.cwd()
    conn = db.connect()
    try:
        rep = proof_store.inventory(
            conn, workspace, scope=getattr(args, "scope", None))
        sweep = consistency.consistency_sweep(
            conn, scope=getattr(args, "scope", None))
    finally:
        conn.close()
    for rel in rep.orphan_files:
        print(f"  [FAIL] orphan proof file (no DB row): {rel}")
    for rel in rep.missing_files:
        print(f"  [FAIL] missing proof file (row past 'open'): {rel}")
    for rel in rep.proved_with_sorry:
        print(f"  [FAIL] proved goal's file carries `sorry`: {rel}")
    sweep_bad = 0
    for cat, rows in sweep.items():
        for r in rows:
            sweep_bad += 1
            print(f"  [FAIL] {cat}: {r}")
    ok = rep.ok() and sweep_bad == 0
    print(f"  [{'  OK' if ok else 'FAIL'}] {rep.summary()}"
          + (f"; tree sweep: {sweep_bad} finding(s)" if sweep_bad
             else "; tree sweep clean"))
    return 0 if ok else 1


def cmd_library_backfill_declinfo(args: argparse.Namespace) -> int:
    """One-shot v24 backfill: re-run the bridge's declInfo pass over every
    already-bridged problem so `library_decls.{signature, decl_kind,
    docstring, src_line}` are filled for pre-oracle harvests too (new
    bridges persist them inline). Idempotent — re-running overwrites with
    the same kernel-true facts. Needs a warm gateway (started here);
    best-effort per file, same contract as the bridge-time pass."""
    from ..lsp import lifecycle as gateway_lifecycle
    from ..pipeline.librarian.bridge import _backfill_decl_signatures
    workspace = Path.cwd()
    conn = db.connect()
    try:
        probs = [str(r["name"]) for r in conn.execute(
            "SELECT DISTINCT p.name FROM problems p"
            " JOIN library_decls ld ON ld.problem = p.name"
            " WHERE p.library_bridged_at IS NOT NULL"
            " AND ld.lifecycle IN ('migrated','cleaned')"
            " ORDER BY p.name")]
        only = getattr(args, "scope", None)
        if only:
            probs = [p for p in probs if only in p]
        if not probs:
            print("nothing to backfill")
            return 0
        gateway_lifecycle.start_gateway(workspace)
        for i, prob in enumerate(probs, 1):
            # resume-friendly: a problem whose placed rows all carry
            # src_line is done (oracle-miss rows re-elaborate on --force)
            missing = conn.execute(
                "SELECT COUNT(*) FROM library_decls WHERE problem = ?"
                " AND lifecycle IN ('migrated','cleaned')"
                " AND src_line IS NULL", (prob,)).fetchone()[0]
            if not missing and not getattr(args, "force", False):
                print(f"[{i}/{len(probs)}] {prob} — complete, skipped",
                      flush=True)
                continue
            print(f"[{i}/{len(probs)}] {prob}", flush=True)
            _backfill_decl_signatures(conn, problem=prob, workspace=workspace)
        n_total, n_done = conn.execute(
            "SELECT COUNT(*), SUM(src_line IS NOT NULL) FROM library_decls"
            " WHERE lifecycle IN ('migrated','cleaned')").fetchone()
        print(f"done: {n_done}/{n_total} placed decls carry declInfo facts")
    finally:
        conn.close()
    return 0


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
        ("formalizer.model", _cc.resolve_model("formalizer")),
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


def cmd_paper_add(args: argparse.Namespace) -> int:
    """Shelve a paper: content-hash identity, PDF → page-anchored
    normalized text (paper_pipeline_design.md D7/D8). Idempotent."""
    from ..papers import shelf
    src = Path(args.file)
    if not src.is_file():
        print(f"ERROR: no such file: {src}")
        return 1
    try:
        meta = shelf.add_paper(Path.cwd(), src, added_by="user",
                               force=bool(getattr(args, "force", False)))
    except (shelf.ScannedPdfError, ValueError) as e:
        print(f"ERROR: {e}")
        return 1
    print(f"OK: paper {meta.id} — bind with `paper: {meta.id}` in the "
          f"Manifest frontmatter; build the map with "
          f"`asterism paper-index {meta.id}`")
    return 0


def cmd_paper_index(args: argparse.Namespace) -> int:
    """Build/rebuild a shelved paper's navigation map (one-shot LLM
    spawn; small docs are exempt — see paper_pipeline_design.md D9)."""
    from ..papers import index as paper_index
    from ..pipeline import PROMPT_DIR
    try:
        out = paper_index.generate_index(
            Path.cwd(), args.id, prompt_dir=PROMPT_DIR,
            force=bool(args.force))
    except (FileNotFoundError, RuntimeError) as e:
        print(f"ERROR: {e}")
        return 1
    print(f"OK: {out}" if out else "OK: exempt (no index needed)")
    return 0


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
        help="whole-Library coherence gate: DB<->disk consistency "
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
    p_review.add_argument("--fresh", action="store_true",
                          help="recompute the closure live (warms the "
                               "gateway) instead of reading the Ingest-time "
                               "snapshot; refreshes the stored snapshot")
    p_review.set_defaults(func=cmd_review)

    p_daemon = sub.add_parser(
        "daemon",
        help="daemon lifecycle: detached start / graceful stop / status "
             "(frontend charter §5-3; the serve API's backend)")
    p_daemon.add_argument("daemon_action",
                          choices=("start", "stop", "status"))
    p_daemon.add_argument("--scope", default=None,
                          help="start: restrict dispatch (SQL LIKE)")
    p_daemon.add_argument("--once", action="store_true",
                          help="start: exit when queue empties")
    p_daemon.add_argument("--wait-lock", type=float, default=0.0,
                          dest="wait_lock",
                          help="start: retry a lock refusal for up to this "
                               "many seconds (the code-drift handoff relay)")
    p_daemon.add_argument("--force", action="store_true",
                          help="stop: terminate immediately instead of "
                               "graceful drain")
    p_daemon.add_argument("--workspace", default=None,
                          help="workspace root (default: resolve_workspace)")
    p_daemon.set_defaults(func=cmd_daemon)

    p_serve = sub.add_parser(
        "serve",
        help="run the localhost web UI (FastAPI; frontend charter §0)")
    p_serve.add_argument("--port", type=int, default=8642,
                         help="bind port (default 8642; host is 127.0.0.1)")
    p_serve.add_argument("--workspace", default=None,
                         help="workspace root (default: resolve_workspace)")
    p_serve.set_defaults(func=cmd_serve)

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

    p_approve = sub.add_parser(
        "approve-ingest",
        help="approve a paused ingest → harvest deliverables to Library")
    p_approve.add_argument("problem", help="problem name")
    p_approve.add_argument("--signer", default=None,
                           help="who signs off (the record also captures "
                                "the machine's own evidence: Claude login, "
                                "OS user, host, content seal)")
    p_approve.set_defaults(func=cmd_approve_ingest)

    p_reject_ingest = sub.add_parser(
        "reject-ingest",
        help="reject a paused ingest (not done yet) → back to proving")
    p_reject_ingest.add_argument("problem", help="problem name")
    p_reject_ingest.add_argument("--reason", default=None,
                                 help="what's still missing (guides the Strategist)")
    p_reject_ingest.set_defaults(func=cmd_reject_ingest)

    p_regress = sub.add_parser(
        "regress",
        help="regression-manifest report: recorded proved/harvested "
             "problems vs the current workspace (re-verify candidates)")
    p_regress.set_defaults(func=cmd_regress)

    p_drift = sub.add_parser(
        "drift-check",
        help="DB<->file consistency gate (orphan / missing / proved-with-sorry)")
    p_drift.add_argument(
        "--scope", type=str, default=None, metavar="PROBLEM",
        help="limit to a problem (LIKE pattern), e.g. residue_thm")
    p_drift.set_defaults(func=cmd_drift_check)

    p_repin = sub.add_parser(
        "repin",
        help="acknowledge a deliberate user-file edit: re-baseline "
             "Manifest.md/Root.lean/Defs.lean so root_integrity_gate "
             "accepts the current content (bytes only — a changed "
             "statement meaning needs re-init/sync)")
    p_repin.add_argument("problem", type=str,
                         help="problem name, e.g. Putnam.putnam_2025_b6")
    p_repin.add_argument(
        "--file", type=str, default=None,
        choices=["Manifest.md", "Root.lean", "Defs.lean"],
        help="re-baseline only this file (default: all present)")
    p_repin.set_defaults(func=cmd_repin)

    p_revive = sub.add_parser(
        "revive",
        help="re-enter a REVOKED problem (post-Ingest un-prove "
             "quarantine) into the live path — the operator's re-grind "
             "decision; the seal-tear/un-harvest already ran automatically")
    p_revive.add_argument("problem", type=str,
                          help="problem name in state 'revoked'")
    p_revive.set_defaults(func=cmd_revive)

    p_kstats = sub.add_parser(
        "knowledge-stats",
        help="offline knowledge-layer telemetry (presearch citation "
             "canary / hint-probe free wins / lesson counts; read-only)")
    p_kstats.add_argument(
        "--problem", type=str, default=None, metavar="LIKE",
        help="SQL LIKE filter, e.g. 'Putnam.%%'")
    p_kstats.set_defaults(func=cmd_knowledge_stats)

    p_libbackfill = sub.add_parser(
        "library-backfill-declinfo",
        help="one-shot v24 backfill: fill library_decls docstring/src_line "
             "(+signature/kind) from the declInfo oracle for bridged problems")
    p_libbackfill.add_argument(
        "--scope", type=str, default=None, metavar="PROBLEM",
        help="limit to problems whose name contains this substring")
    p_libbackfill.add_argument(
        "--force", action="store_true",
        help="re-elaborate problems already marked complete")
    p_libbackfill.set_defaults(func=cmd_library_backfill_declinfo)

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

    p_paper_add = sub.add_parser(
        "paper-add",
        help="shelve a paper under Papers/<content-hash>/ (PDF extracted "
             "to page-anchored text; .md/.txt/.tex pass through)",
    )
    p_paper_add.add_argument("file", help="path to the paper file")
    p_paper_add.add_argument("--force", action="store_true",
                             help="re-extract over an existing slot")
    p_paper_add.set_defaults(func=cmd_paper_add)

    p_paper_index = sub.add_parser(
        "paper-index",
        help="build a shelved paper's navigation map (one-shot LLM; "
             "small docs exempt)",
    )
    p_paper_index.add_argument("id", help="shelf id (from paper-add)")
    p_paper_index.add_argument("--force", action="store_true",
                               help="index even below the small-doc bar")
    p_paper_index.set_defaults(func=cmd_paper_index)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
