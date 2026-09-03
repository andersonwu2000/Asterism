"""Problem lifecycle: `asterism init`, `asterism init-batch`, `asterism
reset` — problem registration/validation against `problem.json` +
Root.lean/Defs.lean, the DB+filesystem chokepoints (`init_problem`,
`delete_problem`, `wipe_problem_rows`) other surfaces (serve API) call
directly, and the reset sweep over the satellite registry. Split out of
`Tooling/core/cli.py` (task A3, move-only) into the `core/cli/` package;
`Tooling/core/cli/__init__.py` re-exports this module's public (and
tested private) surface."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .. import fsutil
from ...state import brief, db, project_docs, satellites, tree
from ...state import intent as intent_mod
from .run import daemon_status


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
# moved to state/intent.py (task #120: the root gate's statement pin
# must read the exact same bytes cmd_init/amend extract). Re-exported
# under the old names for the existing importers (amend, tests).
_ROOT_STATEMENT_RE = intent_mod.ROOT_STMT_STUB_RE
_extract_root_statement = intent_mod.extract_root_statement


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

    The problem's definition comes from `Problems/<problem>/problem.json`
    (the durable seed: charter required; word / settings / papers
    optional — v40, Manifest.md retired). A problem already registered
    with a non-empty charter re-inits from the DB when no seed exists.
    Defs.lean / Root.lean stay optional — see the Phase 6 comment
    below. Returns (0, ok-message) or (1, failure-message); never
    prints.
    """
    msgs: list[str] = []
    pdir = db.problem_dir(workspace, problem)
    if not pdir.is_dir():
        return 1, f"FAIL: {pdir} not found"
    try:
        seed = intent_mod.read_seed(intent_mod.seed_path(workspace, problem))
    except Exception as e:  # noqa: BLE001 — malformed authoring input
        return 1, f"FAIL: problem.json did not parse: {e}"

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
    #                   from the charter (Forward defs/claims +
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
        from ...pipeline._lake import lake_build
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
            "INSERT INTO problems (name, created_at) VALUES (?, ?)",
            (problem, db.now()),
        )
    # v48 (human_interface_design.md §3.1) — every problem belongs to a
    # Project. The dotted prefix is the DEFAULT filing, applied once at
    # registration; a later rename is the Project table's business and a
    # re-init must not undo it, so this never overwrites a filed problem.
    from ...state import projects as _projects
    _projects.ensure_for_problem(conn, problem)
    # v35 — every problem has a top discussion group, its human-facing
    # one. Unconditional (not gated on `existing`): a problem initialised
    # before v35 and re-inited afterwards must acquire one too, and a
    # problem without a group has no seat for its Strategist at all.
    # v40 — the top group's charter IS the problem's goal: seeded from
    # problem.json here; with no seed, a still-empty charter is a FAIL
    # (a problem with no goal has nothing to judge anything against).
    from ...state import groups as _groups
    _groups.ensure_top_group(
        conn, problem,
        charter=str(seed.get("charter", "")).strip() if seed else "")
    if seed is not None:
        # Re-init with a seed refreshes charter/word from it (the seed
        # is what the user authored; the writers record history +
        # re-mirror). Unchanged values are skipped so a re-run of init
        # stays history-idempotent — a 'repin' row is an ack of a
        # CHANGE, not of a rerun.
        cur = intent_mod.read(conn, problem)
        seed_charter = str(seed.get("charter", "")).strip()
        if cur is None or cur.charter != seed_charter:
            intent_mod.set_charter(conn, problem, seed_charter,
                                   source="observed" if existing is None
                                   else "repin")
        word = str(seed.get("word", "") or "").strip()
        if cur is None or cur.word != word:
            intent_mod.set_word(conn, problem, word,
                                source="observed" if existing is None
                                else "repin")
    top = _groups.top_group(conn, problem)
    if top is None or not str(top["charter"]).strip():
        conn.commit()
        return 1, (f"FAIL: {problem} has no charter — write "
                   f"Problems/{problem}/problem.json with a 'charter' "
                   f"field (the problem's goal), or author the problem "
                   f"via the UI.")

    if statement is None:
        # Pure-NL: no root goal row. The problem starts with zero goals —
        # structurally stalled — so the T4 stall wake bootstraps the
        # Strategist's first Inject from the charter alone.
        msgs.append(
            f"OK: init {problem} (pure-NL — no Root.lean; the Strategist "
            f"bootstraps from the charter)")
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
    # Seed papers + settings from problem.json (idempotent; keys/rows
    # already in the DB are never clobbered — settings.write upserts,
    # bind_paper dedups).
    if seed is not None:
        seed_papers = [str(pid) for pid in (seed.get("papers") or [])]
        if seed_papers:
            # A seeded id may name a paper on ANOTHER Project's shelf
            # (§3.9); copy it here first, or the binding points at a
            # document this Project cannot open.
            from ...papers import shelf as _shelf
            from ...state import projects as _projects_mod
            _proj = (_projects_mod.project_of(conn, problem)
                     or problem.split(".", 1)[0])
            for pid in seed_papers:
                _shelf.copy_into_project(workspace, pid, _proj)
                db.bind_paper(conn, problem=problem, paper_id=pid,
                              origin="user")
        from ...state import settings as _settings
        stored = _settings.read(conn, problem)
        for key, val in (seed.get("settings") or {}).items():
            if key in _settings.SETTING_KEYS and key not in stored:
                try:
                    _settings.write(conn, problem, key, val)
                except ValueError as e:
                    msgs.append(f"WARN: settings.{key} skipped ({e})")
    # Refresh the durable seed from the DB (creates problem.json for a
    # DB-authored problem; a seeded init round-trips byte-stable).
    intent_mod.write_seed(conn, workspace, problem)
    # Initial TREE.md so readers see structure right after init.
    tree.write(conn, workspace, problem)
    # Initial BRIEF.md — framework-rendered cross-spawn stable context
    # (sandbox / forbidden lemmas / goal / user word / library).
    # Refreshed at daemon startup if the intent changed.
    pintent = intent_mod.read(conn, problem)
    if pintent is not None:
        brief.write(workspace, pintent, conn=conn)
    # No LESSONS.md seed: Phase 12 Model B made the KB the lessons SoT —
    # reflection writes `kb_entries`, Context reads `kb.query`; the old flat
    # LESSONS.md mirror (and its Edit-anchor seed) is retired.
    return 0, "\n".join(msgs)


def cmd_init_batch(args: argparse.Namespace) -> int:
    """Bulk-init every Problem dir under <root> that has a problem.json.

    Walks `<root>` recursively to locate `problem.json` seeds. Each
    seed's parent directory is treated as a Problem directory; the
    problem slug is derived from its path relative to
    `<workspace>/Problems/` with `/` → `.`.

    Examples:
      Problems/sylvester_gallai/problem.json     → slug 'sylvester_gallai'
      Problems/Minif2f/algebra_1/problem.json    → slug 'Minif2f.algebra_1'

    `<root>` may be the workspace's `Problems/` itself (init everything
    not yet in DB) or any subtree (e.g. `Problems/Minif2f` to init only
    a benchmark batch).

    Idempotent: subdirs already in the DB stay put (cmd_init's own
    idempotency). Failures are reported per-problem; the batch keeps
    going so one broken seed doesn't block the rest.
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

    # `_docs/` is the Project's document tree (HID §3.6), not a problem.
    seeds = [p for p in sorted(root.rglob(intent_mod.SEED_FILENAME))
             if project_docs.ROOT_DIRNAME not in p.parts]
    if not seeds:
        print(f"OK: init-batch {root}: no {intent_mod.SEED_FILENAME} "
              f"found", flush=True)
        return 0

    initialized: list[str] = []
    failed: list[tuple[str, str]] = []
    for mpath in seeds:
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

    Doesn't touch proof files / Root.lean / problem.json. Operator runs
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
            from ...state.thresholds import SHELVE_THRESHOLD as _ST
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
#: problem — read from the satellite registry (`state/satellites.py`),
#: which is the one home for "what does a problem own on disk": the
#: sweeper, the verifier and the complement audit all read the same
#: entries, so none of them can drift into a private blind spot the
#: way the pre-d45a17b9 duplicated tuple did.
PROOFS_SWEEP_PATTERNS = satellites.swept(satellites.SCOPE_PROOFS)


def cmd_reset(args: argparse.Namespace) -> int:
    """Wipe one Problem's DB rows + on-disk `proofs/` files. User-owned
    files (`problem.json`, `Defs.lean`, `Root.lean`) and anything outside
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

    Refuses to reset if no problem.json exists (signals user typo, and
    guards against a reset the subsequent re-init could not recover
    from — the seed is what re-init runs on).
    """
    if getattr(args, "soft", False):
        return _soft_reset(args.problem)

    workspace = Path.cwd()
    problem = args.problem
    pdir = db.problem_dir(workspace, problem)
    if not pdir.exists():
        print(f"FAIL: Problems/{problem}/ not found", file=sys.stderr)
        return 1
    seed_file = intent_mod.seed_path(workspace, problem)
    if not seed_file.exists():
        print(f"FAIL: {seed_file} not found — reset would be "
              f"unrecoverable (re-init seeds from problem.json)",
              file=sys.stderr)
        return 1

    conn = db.connect()
    db.init_schema(conn)
    conn.execute("PRAGMA foreign_keys = ON")
    n_goals, n_strats = wipe_problem_rows(conn, problem)
    conn.commit()
    # DB complement audit, REPORT ONLY: rows still referencing this
    # problem in any table the schema-derived classification can ask
    # (state/satellites.py). A non-zero count is a wipe blind spot —
    # reported for the operator, never auto-deleted: widening what
    # reset destroys is a human decision made on this evidence.
    leftover_rows = satellites.db_leftovers(conn, problem)
    if leftover_rows:
        print(f"  Note: DB rows still referencing {problem} after the "
              f"wipe (left in place — a wipe blind spot to triage):")
        for table, n in sorted(leftover_rows.items()):
            print(f"    ? {table}: {n} row(s)")
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
    # Each target kind needs BOTH sweeps: the dead_attempts rows that
    # NAME the referent (done above, by id) and the ones that merely
    # HANG OFF its pipeline by FK. The Problem and Group kinds got their
    # second sweep below; Goal and Strategy never had one, because every
    # dead_attempt of theirs was assumed to name its goal. The failure
    # SENTINEL breaks that assumption — `target_id=0` for a failure
    # about no goal at all (satellites.DEAD_ATTEMPT_NO_TARGET), with
    # `target_kind` copied from the pipeline's own kind — so a sentinel
    # off a Goal- or Strategy-kind pipeline matched neither sweep and
    # stranded on the `DELETE FROM pipelines` here, FK and all. Today
    # every write site happens to be Strategist/Forward/Librarian, which
    # is a fact about the callers, not about the schema.
    if gids:
        ph = ",".join("?" * len(gids))
        conn.execute(
            f"DELETE FROM dead_attempts WHERE pipeline_id IN "
            f"(SELECT id FROM pipelines WHERE target_kind='Goal' "
            f" AND target_id IN ({ph}))", [str(g) for g in gids])
        conn.execute(
            f"DELETE FROM pipelines WHERE target_kind='Goal' "
            f"AND target_id IN ({ph})", [str(g) for g in gids])
    if sids:
        ph = ",".join("?" * len(sids))
        conn.execute(
            f"DELETE FROM dead_attempts WHERE pipeline_id IN "
            f"(SELECT id FROM pipelines WHERE target_kind='Strategy' "
            f" AND target_id IN ({ph}))", [str(s) for s in sids])
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
    #
    # Two key shapes live in `pipelines.target_id` under this one kind:
    # the bare problem name (Forward) and the Librarian's composed
    # `problem\x1ffile` unit key. An exact `= ?` reads only the first,
    # so every per-file Librarian row outlived its problem — the same
    # gap as the Group targets above, found the same day by the same
    # audit, and larger. Both callers ask through the ONE decoder in
    # `state.satellites`, so the wipe and the auditor cannot disagree
    # about which rows belong to a problem (they did, 1,063 times).
    _tgt = satellites.PROBLEM_OF_TARGET
    conn.execute(
        f"DELETE FROM dead_attempts WHERE pipeline_id IN "
        f"(SELECT id FROM pipelines WHERE target_kind='Problem' "
        f" AND {_tgt} = ?)",
        (problem,),
    )
    conn.execute(
        f"DELETE FROM pipelines WHERE target_kind='Problem' "
        f"AND {_tgt} = ?",
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
    # Discussion groups (v35), and the polymorphic rows that TARGET them.
    #
    # The target-kind list in this function was written when there were
    # three kinds; v35 added a fourth and only the `groups` row itself
    # was swept, so every Group-targeted pipeline and dead_attempt
    # outlived its group — 68 pipelines + 54 dead_attempts measured
    # 2026-08-14, the oldest from the 2026-07 sub-group runs. Nothing
    # broke, which is why it survived: the rows are invisible until a
    # forensics query joins through a group id that no longer resolves.
    # (Ruling: delete, 2026-08-14. Task #208.)
    #
    # Ids first, rows after: once `groups` is gone the question "which
    # groups did this problem own" is unanswerable and only the global
    # orphan audit can see the leftovers.
    grids = [str(r[0]) for r in conn.execute(
        "SELECT id FROM groups WHERE problem = ?", (problem,)).fetchall()]
    if grids:
        ph = ",".join("?" * len(grids))
        # dead_attempts.pipeline_id → pipelines FK: both the rows that
        # NAME a group and the rows that hang off a group's pipeline
        # must go before the pipelines themselves.
        conn.execute(
            f"DELETE FROM dead_attempts WHERE target_kind='Group' "
            f"AND target_id IN ({ph})", grids)
        conn.execute(
            f"DELETE FROM dead_attempts WHERE pipeline_id IN "
            f"(SELECT id FROM pipelines WHERE target_kind='Group' "
            f" AND target_id IN ({ph}))", grids)
        conn.execute(
            f"DELETE FROM pipelines WHERE target_kind='Group' "
            f"AND target_id IN ({ph})", grids)
    # Order-independent by construction: the self-FK cascades to
    # descendants (a sub-group carries its ancestor's `problem`, so the
    # id sweep above covers the whole subtree) and the two mutual
    # references with strategist_decisions are both ON DELETE SET NULL —
    # this table and that one point at each other, so no delete order is
    # right for both.
    conn.execute("DELETE FROM groups WHERE problem = ?", (problem,))
    # Spend telemetry (v21). It used to survive both reset and problem
    # deletion, on the reasoning that money already spent is a record of
    # the world rather than of run state — 2,351 rows for a
    # putnam_2025_b6 that no longer exists, measured 2026-08-14. The
    # owner ruled otherwise: the accounting is per-problem, so it leaves
    # with the problem. Nothing reads it across a reset boundary
    # (`knowledge_stats` joins pipelines, `serve.data` groups by
    # problem), so the rows had no reader that outlived their subject.
    conn.execute("DELETE FROM spawn_usage WHERE problem = ?", (problem,))
    # Schema-DERIVED backstop for everything above. Every DELETE in this
    # function names its table by hand, and a hand list cannot notice a
    # table added after it was written — `human_commands` (v48) and
    # `routine_verdicts` (2026-08-30) both carry `problem ... REFERENCES
    # problems(name)` and neither was ever added, so a reset on a problem
    # holding either row died on the FK at the `DELETE FROM problems`
    # below, before the leftovers report meant to catch this could run.
    # Naming those two here would fix the instance and keep the class;
    # asking the schema which tables are problem-keyed (the same
    # derivation `db_leftovers` audits with) ends it. The passes above
    # stay — they clear the goal/strategy/group-keyed rows no `problem`
    # column can express, and they leave this sweep a no-op for every
    # table they already named.
    for _t in satellites.problem_column_sweep_order(conn):
        conn.execute(f"DELETE FROM {_t} WHERE problem = ?", (problem,))
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
    # `.asterism/runtime_slots/`; the workspace-root patterns are
    # retained for migration cleanup of pre-move daemons. Patterns and
    # their rationale live in the satellite registry.
    runtime_slots = workspace / ".asterism" / "runtime_slots"
    if runtime_slots.exists():
        for pattern in satellites.swept(satellites.SCOPE_RUNTIME_SLOTS):
            for f in runtime_slots.glob(pattern):
                if _robust_unlink(f):
                    deleted_files.append(f"{runtime_slots.name}/{f.name}")
                else:
                    failed_files.append(f.name)
    for pattern in satellites.swept(satellites.SCOPE_WORKSPACE):
        for f in workspace.glob(pattern):
            if _robust_unlink(f):
                deleted_files.append(f.name)
            else:
                failed_files.append(f.name)

    # Per-problem artifacts that aren't in proofs/ — the swept names,
    # the kept names (problem.json/Defs/Root/BRIEF) and the reason for
    # each are the registry's to state, not this loop's.
    for name in satellites.swept(satellites.SCOPE_PROBLEM_ROOT):
        p = pdir / name
        if p.exists():
            if _robust_unlink(p):
                deleted_files.append(name)
            else:
                failed_files.append(name)

    # Run-scoped directories (.drafts / .presearch / .groups): all three
    # carry id-keyed or worldview state that must not leak into a rerun
    # — each entry's `why` in the registry records the specific hazard.
    for name in satellites.swept(satellites.SCOPE_PROBLEM_ROOT, dirs=True):
        d = pdir / name
        if d.exists():
            if not _robust_rmtree(d):
                failed_files.append(f"{name}/")

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
    # behavior: auto-rewrite from the retired Manifest statement, which is no
    # longer the canonical source.)
    root_lean = pdir / "Root.lean"

    # Post-reset verification: every SWEPT registry entry, re-checked.
    # Derived from the same registry the sweeper read, so the verifier
    # cannot lag the sweep list — and it now covers every swept entry
    # (PROGRAMME.md / _plan.md / the three dot-dirs included), where the
    # old hand-list re-checked only a subset. It catches "unlink
    # reported success but the file came back" (a process still
    # spawning) as well as a registry entry the loops above mishandled.
    leftovers: list[str] = []
    if proofs_dir.exists():
        for pattern in satellites.swept(satellites.SCOPE_PROOFS):
            for f in proofs_dir.glob(pattern):
                leftovers.append(f"proofs/{f.name}")
    for name in satellites.swept(satellites.SCOPE_PROBLEM_ROOT):
        if (pdir / name).exists():
            leftovers.append(name)
    for name in satellites.swept(satellites.SCOPE_PROBLEM_ROOT, dirs=True):
        if (pdir / name).exists():
            leftovers.append(f"{name}/")
    runtime_slots = workspace / ".asterism" / "runtime_slots"
    if runtime_slots.exists():
        for pattern in satellites.swept(satellites.SCOPE_RUNTIME_SLOTS):
            for f in runtime_slots.glob(pattern):
                leftovers.append(f"{runtime_slots.name}/{f.name}")
    for pattern in satellites.swept(satellites.SCOPE_WORKSPACE):
        for f in workspace.glob(pattern):
            leftovers.append(f.name)
    if leftovers:
        print(f"FAIL: reset {problem}: cleanup verified, but these "
              f"files reappeared / weren't matched:",
              file=sys.stderr)
        for name in leftovers:
            print(f"  - {name}", file=sys.stderr)
        return 2

    # Complement audit, REPORT ONLY: anything present that NO registry
    # entry claims — swept or kept. This is the question the verifier
    # above structurally cannot ask (it only re-checks what the sweeper
    # already knows), and the d45a17b9 lesson is that the two must not
    # share a source. An unclaimed path may be the framework's next
    # unregistered artifact or the user's own file, which is exactly
    # why nothing here deletes: register it, or ignore it, is the
    # operator's call.
    unclaimed = satellites.file_complement(pdir)
    if unclaimed:
        print(f"  Note: {len(unclaimed)} path(s) in the problem dir "
              f"that no satellite-registry entry claims (kept, not "
              f"touched — register framework artifacts in "
              f"state/satellites.py):")
        for name in unclaimed:
            print(f"    ? {name}")

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
