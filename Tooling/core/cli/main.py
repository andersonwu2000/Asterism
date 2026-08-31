"""`main()` — the `asterism` argparse CLI: every `sub.add_parser` call and
the `cmd_*` dispatch wiring. Split out of `Tooling/core/cli.py` (task A3,
move-only) into the `core/cli/` package; `Tooling/core/cli/__init__.py`
re-exports `main` (the `pyproject.toml` console-script entry point,
`Tooling.core.cli:main`, resolves through the facade unchanged)."""
from __future__ import annotations

import argparse

from .diagnose import (
    cmd_config,
    cmd_doctor,
    cmd_drift_check,
    cmd_knowledge_stats,
    cmd_library_verify,
    cmd_logs,
    cmd_regress,
    cmd_review,
    cmd_status,
)
from .maint import (
    cmd_approve_ingest,
    cmd_charter,
    cmd_kb_migrate,
    cmd_library_backfill_declinfo,
    cmd_paper_add,
    cmd_paper_index,
    cmd_prune,
    cmd_reject,
    cmd_reject_ingest,
    cmd_repin,
    cmd_bench,
    cmd_revive,
    cmd_unbench,
    cmd_word,
)
from .problems import cmd_init, cmd_init_batch, cmd_reset
from .run import _force_utf8_io, cmd_daemon, cmd_run, cmd_serve


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
        help="bulk-init every <root>/<subdir>/ that has a problem.json",
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
        help="pre-flight: tools / Asterism.yaml / problems / .attempts state",
    )
    p_doctor.add_argument(
        "--cloud", action="store_true",
        help="Oracle ARM64 cloud readiness checks instead of the desktop "
             "set: OS/arch, CPU/RAM/disk, cgroup v2 visibility, python/"
             "node/provider presence, Lean toolchain + leantar arch, "
             "8642/8765/8898 bind posture",
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

    p_catverify = sub.add_parser(
        "catalog-verify",
        help="cold-build every proof module of a problem through the build "
             "lease; map failing modules to strategies/goals; --rollback "
             "hands culprits to rollback_cascade_chain (daemon must be stopped)",
    )
    p_catverify.add_argument("--scope", default=None, metavar="PROBLEM",
                             help="one problem (default: every problem)")
    p_catverify.add_argument("--rollback", action="store_true",
                             help="roll back every failing brick (refuses "
                                  "while a daemon owns the DB)")
    from .catalog_verify import cmd_catalog_verify
    p_catverify.set_defaults(func=cmd_catalog_verify)

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
             "Root.lean/Defs.lean/charter/word so root_integrity_gate "
             "accepts the current content (bytes only — a changed "
             "statement meaning needs re-init/sync)")
    p_repin.add_argument("problem", type=str,
                         help="problem name, e.g. Putnam.putnam_2025_b6")
    p_repin.add_argument(
        "--file", type=str, default=None,
        choices=["Root.lean", "Defs.lean", "charter", "word"],
        help="re-baseline only this file (default: all present)")
    p_repin.set_defaults(func=cmd_repin)

    p_charter = sub.add_parser(
        "charter",
        help="show or set the problem's goal (the top group's charter); "
             "DB-resident since v40, live on the next spawn")
    p_charter.add_argument("problem", type=str,
                           help="problem name")
    p_charter.add_argument(
        "--file", type=str, default=None, metavar="PATH",
        help="set the charter from this file's content (your scratch "
             "draft — the durable copy is problem.json, refreshed "
             "automatically)")
    p_charter.set_defaults(func=cmd_charter)

    p_word = sub.add_parser(
        "word",
        help="show or set the user's word (standing directives, every "
             "group at every depth); DB-resident, live on the next spawn")
    p_word.add_argument("problem", type=str, help="problem name")
    p_word.add_argument(
        "--file", type=str, default=None, metavar="PATH",
        help="set the word from this file's content")
    p_word.add_argument(
        "--clear", action="store_true",
        help="withdraw all standing directives (set the word empty)")
    p_word.set_defaults(func=cmd_word)

    p_revive = sub.add_parser(
        "revive",
        help="re-enter a REVOKED problem (post-Ingest un-prove "
             "quarantine) into the live path — the operator's re-grind "
             "decision; the seal-tear/un-harvest already ran automatically")
    p_revive.add_argument("problem", type=str,
                          help="problem name in state 'revoked'")
    p_revive.set_defaults(func=cmd_revive)

    p_bench = sub.add_parser(
        "bench",
        help="take a problem off the live path without touching its "
             "state — no dispatch, no Strategist seats (owner's "
             "'hopeless for now' lever; `unbench` reverses)")
    p_bench.add_argument("problem", type=str, help="problem name")
    p_bench.set_defaults(func=cmd_bench)

    p_unbench = sub.add_parser(
        "unbench", help="put a benched problem back on the live path")
    p_unbench.add_argument("problem", type=str, help="problem name")
    p_unbench.set_defaults(func=cmd_unbench)

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
