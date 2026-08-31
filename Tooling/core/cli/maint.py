"""Remaining operational commands: `asterism reject`, `asterism
approve-ingest`/`reject-ingest` (anchor+claim sign-off), `asterism repin`/
`charter`/`word` (user-intent baselines), `asterism revive`, `asterism
library-backfill-declinfo`, `asterism prune`, `asterism paper-add`/
`paper-index`, `asterism kb-migrate`. Split out of `Tooling/core/cli.py`
(task A3, move-only) into the `core/cli/` package; `Tooling/core/cli/
__init__.py` re-exports this module's public (and tested private)
surface."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ...quality import prune
from ...state import db, kb, kb_ingest
from ...state import intent as intent_mod


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
    from ...pipeline._constants import canonicalize_anchor_pending
    victims: list[tuple[int, str]] = []
    warnings: list[tuple[str, str]] = []
    # Same scope as the sign-off page this pairs with: a person can only
    # reject a claim they were shown, so the cascade may only walk the
    # top group's deliverables (`db.deliverables`).
    for d in db.deliverables(conn, problem=problem,
                             group_id=db.top_group_id(conn, problem)):
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
    from ...lsp import lifecycle as gateway_lifecycle
    from ...pipeline._constants import anchor_closure_goal
    from ...state import transitions

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
    the `problem_settings` row; absent/unreadable reads False (no
    harvest without an explicit opt-in — mirrors the `library`
    default)."""
    from ...state import settings as _settings
    val = _settings.read(conn, problem).get("library")
    return val if isinstance(val, bool) else False


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
    from ...state import transitions as _transitions
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
    from ...state import transitions as _transitions
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


def cmd_repin(args: argparse.Namespace) -> int:
    """Operator acknowledgment of a deliberate user-file edit
    (self-audit 2026-07-12 §3-3): record the CURRENT content of the
    problem's user-intent files as 'repin' baselines in
    `user_file_history`, so `root_integrity_gate` accepts the current
    bytes again. NOTE: repin acknowledges BYTES only — if the root
    STATEMENT's meaning changed, `goals.statement` is stale and the
    honest path is re-init (or sync), not repin."""
    workspace = Path.cwd()
    problem = str(args.problem)
    files = ([args.file] if getattr(args, "file", None)
             else list(intent_mod.USER_INTENT_FILES)
             + list(intent_mod.DB_INTENT_KEYS))
    conn = db.connect()
    try:
        if conn.execute("SELECT 1 FROM problems WHERE name = ?",
                        (problem,)).fetchone() is None:
            print(f"[repin] unknown problem {problem!r}")
            return 1
        pdir = db.problem_dir(workspace, problem)
        pintent = intent_mod.read(conn, problem)
        n = 0
        for name in files:
            if name in intent_mod.DB_INTENT_KEYS:
                # DB-resident intent value (v40): re-baseline whatever
                # is currently in the DB (covers a hand-sqlite repair).
                body = (pintent.charter if name == "charter"
                        else pintent.word) if pintent else ""
            else:
                path = pdir / name
                if not path.is_file():
                    continue
                body = path.read_text(encoding="utf-8")
            sha = intent_mod._content_sha(body)
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


def _cmd_intent_value(args: argparse.Namespace, key: str) -> int:
    """Shared body of `asterism charter` / `asterism word` (v40): with
    no flag, print the current value; `--file` sets it from a scratch
    draft (the writers record history and refresh problem.json)."""
    problem = str(args.problem)
    conn = db.connect()
    db.init_schema(conn)
    try:
        pintent = intent_mod.read(conn, problem)
        if pintent is None:
            print(f"[{key}] unknown problem {problem!r}", file=sys.stderr)
            return 1
        src = getattr(args, "file", None)
        clear = bool(getattr(args, "clear", False))
        if src is None and not clear:
            cur = pintent.charter if key == "charter" else pintent.word
            print(cur if cur.strip() else f"({key} is empty)")
            return 0
        body = "" if clear else Path(src).read_text(encoding="utf-8")
        if key == "charter":
            intent_mod.set_charter(conn, problem, body)
        else:
            intent_mod.set_word(conn, problem, body)
        print(f"[{key}] {problem}: updated ({len(body)} chars) — live "
              f"on the next spawn; problem.json refreshed")
        return 0
    finally:
        conn.close()


def cmd_charter(args: argparse.Namespace) -> int:
    return _cmd_intent_value(args, "charter")


def cmd_word(args: argparse.Namespace) -> int:
    return _cmd_intent_value(args, "word")


def cmd_bench(args: argparse.Namespace) -> int:
    """Owner bench (2026-08-31): take a problem off the live path
    WITHOUT touching its state — no refill dispatch, no Strategist
    seats. Unleased queue rows are flushed so nothing already enqueued
    fires; in-flight work finishes on its own. `unbench` reverses."""
    conn = db.connect()
    db.init_schema(conn)
    problem = str(args.problem)
    if conn.execute("SELECT 1 FROM problems WHERE name = ?",
                    (problem,)).fetchone() is None:
        print(f"[bench] unknown problem {problem!r}")
        return 1
    conn.execute("UPDATE problems SET benched = 1 WHERE name = ?",
                 (problem,))
    cur = conn.execute(
        "DELETE FROM queue WHERE problem = ? AND owner_pid IS NULL",
        (problem,))
    conn.commit()
    print(f"[bench] {problem}: benched — no new dispatch or seats; "
          f"flushed {cur.rowcount} queued row(s); state untouched "
          f"(`asterism unbench` to resume).")
    conn.close()
    return 0


def cmd_unbench(args: argparse.Namespace) -> int:
    """Reverse of `bench` — the problem rejoins the live path on the
    next daemon tick."""
    conn = db.connect()
    db.init_schema(conn)
    problem = str(args.problem)
    if conn.execute("SELECT 1 FROM problems WHERE name = ?",
                    (problem,)).fetchone() is None:
        print(f"[unbench] unknown problem {problem!r}")
        return 1
    conn.execute("UPDATE problems SET benched = 0 WHERE name = ?",
                 (problem,))
    conn.commit()
    print(f"[unbench] {problem}: back on the live path.")
    conn.close()
    return 0


def cmd_revive(args: argparse.Namespace) -> int:
    """Problem FSM §2.1: re-enter a REVOKED problem (post-Ingest
    un-prove quarantine) into the live path. The incident announcement
    (seal torn, Library un-harvested) already happened automatically;
    this is the operator's re-grind decision. Clears `ingested_at` so
    the liveness machinery resumes wakes/dispatch."""
    from ...state import transitions as _transitions
    conn = db.connect()
    db.init_schema(conn)
    problem = str(args.problem)
    row = conn.execute("SELECT state FROM problems WHERE name = ?",
                       (problem,)).fetchone()
    if row is None:
        print(f"[revive] unknown problem {problem!r}")
        return 1
    # `refuted` (v46, 2026-08-30) leaves the same way: the operator's
    # re-grind decision after a kernel-disproved root — e.g. the charter
    # was amended and the old refutation no longer applies.
    if str(row["state"]) not in ("revoked", "refuted"):
        print(f"[revive] {problem!r} is {row['state']!r}, not 'revoked' or "
              f"'refuted' — nothing to revive.")
        return 1
    db.set_problem_ingested(conn, problem, ingested=False)
    _transitions.apply_problem_transition(
        conn, problem, "active", event="operator_revived")
    print(f"[revive] {problem}: back on the live path — wakes and "
          f"dispatch resume on the next daemon tick.")
    conn.close()
    return 0


def cmd_library_backfill_declinfo(args: argparse.Namespace) -> int:
    """One-shot v24 backfill: re-run the bridge's declInfo pass over every
    already-bridged problem so `library_decls.{signature, decl_kind,
    docstring, src_line}` are filled for pre-oracle harvests too (new
    bridges persist them inline). Idempotent — re-running overwrites with
    the same kernel-true facts. Needs a warm gateway (started here);
    best-effort per file, same contract as the bridge-time pass."""
    from ...lsp import lifecycle as gateway_lifecycle
    from ...pipeline.librarian.bridge import _backfill_decl_signatures
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


def cmd_paper_add(args: argparse.Namespace) -> int:
    """Shelve a paper: content-hash identity, PDF → page-anchored
    normalized text (paper_pipeline_design.md D7/D8). Idempotent."""
    from ...papers import shelf
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
    print(f"OK: paper {meta.id} — bind it to a problem via the UI; "
          f"build the map with `asterism paper-index {meta.id}`")
    return 0


def cmd_paper_index(args: argparse.Namespace) -> int:
    """Build/rebuild a shelved paper's navigation map (one-shot LLM
    spawn; small docs are exempt — see paper_pipeline_design.md D9)."""
    from ...papers import index as paper_index
    from ...pipeline import PROMPT_DIR
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
