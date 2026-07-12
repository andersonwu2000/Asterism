"""File-size ratchet — stop the biggest modules from silently regrowing.

Each watermark below is the file's line count at the time of the
dedup.py → cleanup/ extraction (2026-06), rounded up to the next multiple
of 50. Existing debt is grandfathered; GROWTH is blocked: a file may
shrink freely, but exceeding its watermark fails this test. If you
legitimately must exceed a limit, prefer splitting the file (as dedup.py
was split into `cleanup/`); only consciously bump the number here — in
the same PR as the growth, so the increase is visible in review.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# {relative path: max line count}
_WATERMARKS = {
    # 1900→1950: run_staged_cleanup_file holds ONE file-level gateway session
    # across the mechanical whole-file gates (strip-comments + decide), so they
    # verify on a warm claimed slot instead of cold `lake env lean` (#35 stage
    # 1b) — 2026-06-19 — conscious bump.
    # 1950→1960: (c2) normalize-whitespace mechanical stage wired into
    # run_staged_cleanup_file before decide/audit — 2026-06-20 — conscious bump.
    # 1960→2020: cross-file bridge import-cycle guard (`_imports_reaches` /
    # `_lib_imports_on_disk`) — reject a bridge whose cited module already
    # transitively imports the bridging file's module (#41) — 2026-06-20.
    "Tooling/quality/librarian/dedup.py": 2020,
    # 2850→2900 classify size gate; →3000 Defs section-context + ownership
    # guard; →3050 same-path race lock; →3100 docstring-aware slicing;
    # →3200 cross-problem shared-def redirect + variable-block dedupe +
    # classify Library-tree context (stokes, 2026-06-11) — conscious bumps.
    # This file is OVERDUE a split (librarian work-kinds → submodules).
    # 3400→3450: _toposort_intra_file Defs-first tie-break — hoist
    # implicitly-used instances (typeclass, never named → no usage edge)
    # above their proof users (stokes PerBumpStokes instBdryOriented migrate
    # build failure) — 2026-06-16 — conscious bump.
    # 3450→3500: per-file cleanup hard Mathlib-PR gate (build must be
    # warning-free → fail unit) + redundant variable-block collapse in
    # _run_cleanup — 2026-06-17 — conscious bump.
    # 3500→3550: _reorder_decls_by_intrafile_refs — post-cleanup re-derive
    # intra-file decl order from the FINAL file's references (dedup/simplify
    # can rewrite a proof to cite a sibling, introducing a forward ref
    # file_order, frozen at classify, never reflects — eckart_young whole-
    # Library build failure) — 2026-06-17 — conscious bump.
    # 3550→3600: migrate hardening for residue_thm shapes — pull `open X in`
    # into the decl's slice (don't hoist a scoped-open above `namespace`) +
    # self_namespaces strip (decls declared under a Mathlib-extending
    # namespace like `Complex.windingNumber`) — 2026-06-17 — conscious bump.
    # 3600→3700: classify size gate accounts for the SCC file merge —
    # `_plan_usage_and_canon` (extracted from commit_classify, shared) +
    # `verify_merged_file_sizes` (reject a usage-cycle group that merges over
    # budget → re-classify, instead of a longFile STALL) — 2026-06-18.
    # 3700→3600: removed 7 dead v0.2/v0.3-vestigial functions (the
    # bridge/cleanup "re-gate the cone" cluster — _regate_touched +
    # _default_regate_build + _snapshot_problem_library + _restore_snapshot +
    # _problem_library_files, superseded by the mechanical bridge Gate B — plus
    # _importers_of + _normalize_stmt) — 2026-06-18 — tighten.
    # 3600→3650→3620: classify carries its rejection across re-dispatch
    # (_classify_feedback_path + compile_librarian_context prev_error, Phase F)
    # — the 3650 also covered Phase G (classify → run_with_session_retries),
    # since reverted (built on a wrong premise + a builder-retry-framing
    # regression), so the ceiling tightened back to the Phase-F level
    # — 2026-06-18.
    # 3620→3680: classify retry is now INCREMENTAL — `_classify_prior_plan_path`
    # carries the prior plan.json and compile_librarian_context hands it back
    # asking for the SMALLEST edit, so a re-emit stops re-dropping a different
    # decl each time (whack-a-mole) — 2026-06-18 — conscious bump.
    # 3680→3760: classify SCC-cycle STALL fix — the layout context now feeds the
    # agent the proof-term USAGE graph in topological order + a file-DAG rule
    # (`_decl_usage`, shared with the gate), the size/cycle retry asks for a
    # RE-PARTITION (not the incremental "smallest edit", which obstructs an
    # SCC break), and `verify_merged_file_sizes` NAMES the cross-file back-edges
    # (`_scc_cross_file_edges`) — 2026-06-18 — conscious bump.
    # 3760→3800: classify watchdog trap_check now scales with the kept-decl
    # count (`_classify_trap_budget` + a per-spawn trap_check_sec override
    # threaded spawn_llm → _watchdog) so a large layout's single long think is
    # not mistaken for a thinking-trap at the flat 660s (residue 271) —
    # 2026-06-18 — conscious bump.
    # 3800→3810: _import_sort_key / _sorted_import_lines — order migrated imports
    # Mathlib-first (before Library.*), because Lean instance resolution is
    # import-order-sensitive (ContinuousSMul ℝ ℂ / IsScalarTower ℝ ℝ ℂ fail to
    # synthesize when `import Mathlib` follows a Library sibling) (#42) — 2026-06-21.
    # 3810→3895: preserve operator-chosen Defs namespaces (`_defs_decl_namespace`
    # / `_ns_is_operator_specified` + `chunk_ns` per-namespace reassembly) so a
    # Defs decl authored under `namespace Complex` keeps `Complex.windingNumber`
    # instead of being relabelled into the Library namespace — Gate B could no
    # longer re-derive the root statement otherwise (#43) — 2026-06-21.
    # SPLIT 2026-06-21: the 3.9k-line `pipeline/librarian.py` monolith was split
    # into a `pipeline/librarian/` package (concern submodules) — watermarks are
    # per-submodule now. `execute.py` is the largest (the migrate executor); a
    # later quality pass may trim it.
    "Tooling/pipeline/librarian/__init__.py": 145,
    "Tooling/pipeline/librarian/_base.py": 150,
    # 400→430 (2026-07-04): declInfo-oracle seams (`oracle=` params +
    # fallback plumbing) in `_defs_decl_source`/`_defs_decl_namespace`;
    # expected to drop back under 400 when the regex paths retire to
    # cold-fallback-only (task: declInfo syntactic oracle).
    # 430→455 (2026-07-05): `alias` command extraction (opt-in
    # include_aliases) — dedupe-bridge one-liners are kernel constants the
    # axiom probe must cover up front (sphere_homology coverage-gap
    # re-probes on `band_aug_coord_sum`).
    "Tooling/pipeline/librarian/astslice.py": 455,
    "Tooling/pipeline/librarian/classify.py": 545,
    "Tooling/pipeline/librarian/schedule.py": 235,
    # 345→360: Gate D namespace-preserved-Defs branch — a #43-preserved Defs
    # decl (`Complex.windingNumber`, same FQN in problem Defs + Library copy)
    # verifies by source equality, NOT the cross-module defeq probe that would
    # import both and die on "environment already contains" (residue migrate
    # STALL) — 2026-06-21.
    # gate 360→385 + bridge 345→390 + run 515→560: post-rewrite axiom gate
    # (2026-07-03) — cleanup's LLM stages (simplify / near-dup bridge / audit
    # whole-file rewrite) run AFTER migrate's per-decl axiom check; re-gate
    # the FINAL text at cleanup exit + the deliverable bridge end (which was
    # builds-only), and hard-fail any `axiom` declaration — conscious bumps.
    # 385→415 (2026-07-04): axiom-probe COVERAGE cross-check + one-shot
    # self-heal — the probe elaboration's decl_info (kernel-true decl list)
    # must all carry `#print axioms` lines; a text-extraction miss used to
    # silently narrow the axiom gate (task: declInfo syntactic oracle).
    # 415→425 (2026-07-05): include_aliases at the probe's extract_decls
    # call (same alias-coverage fix).
    # 425→440 (2026-07-06): inductive-companion exemption in the coverage
    # cross-check (casesOn re-probe class) — conscious bump.
    "Tooling/pipeline/librarian/gate.py": 440,
    "Tooling/pipeline/librarian/context.py": 430,
    "Tooling/pipeline/librarian/execute.py": 1170,  # +universe hoist/dedup (#72)
    "Tooling/pipeline/librarian/bridge.py": 390,
    "Tooling/pipeline/librarian/run.py": 560,
    # dispatcher 2750→2800 + db 2450→2500: awaiting_human observability
    # (startup + idle-exit log of paused problems) + scope-aware idle exit
    # via db.dispatchable_open_goals — a paused P12 read as a multi-hour
    # hang across two sessions (2026-06-12) — conscious bumps.
    # dispatcher 2800→2900 + db 2500→2600: reconcile_stuck_states — per-tick
    # safety net for orphaned pending_review + NULL-outcome Inject wedges
    # (db.problems_with_pending_review / null_inject_redispatch_specs /
    # queue_has_decision) — 2026-06-13 — conscious bumps.
    # db 2600→2650: routine-only T1 clock (last_routine_at + daemon-start
    # baseline + drop batch suppression) so the routine audit fires on its own
    # running-time cadence — 2026-06-13 — conscious bump.
    # db 2650→2750: reconcile_settled_inject_outcomes — resolve NULL-outcome
    # Inject decisions whose produced goal/strategy settled (incl. the
    # soft-shelved-subgoal deadlock that wedged P13) so they stop suppressing
    # the T4 stall trigger — 2026-06-13 — conscious bump.
    # 2026-06-14: Phase 11 'stalled' strategy status (parent-stall transition +
    # migration + reconcile backstop rework) — conscious bump.
    # dispatcher 2980→3050: PID-reuse-proof singleton lock (store pid+start_time,
    # _proc_start_time / _cmdline_is_daemon / _lock_held_by_live_daemon) — a
    # crashed daemon's reused PID had blocked every restart (2026-06-15) —
    # conscious bump.
    # db 2880→3000: shelved no longer settles an inject (P13 4284 spin fix) —
    # `has_active_inflight_inject` (stall predicate) + `has_live_inflight_inject`
    # (T0 / verify-guard suppression) + parked-target redispatch guard —
    # 2026-06-15 — conscious bump.
    # db 3000→3050: #2 `goals_reachable_excluding` (DAG-aware cascade) + #4
    # `outcome_detail` column + `set_inject_decision_outcome_detail` (decline
    # `## Why` → Strategist) — 2026-06-15 — conscious bump.
    # db 3050→3100: null_inject_redispatch_specs collapses NULL Builder/Backward
    # injects to the latest per (target,kind) — restore one in-flight worker per
    # goal on restart, not N racing workers (P13 4284 909/911/920) — 2026-06-15.
    # dispatcher 3050→3080: cascade_one missing_parent_stub → terminal shelve
    # (stop the instant no-cooldown re-dispatch spin on a goal whose own stub
    # file vanished — DB↔file drift, P13 g4437) — 2026-06-16 — conscious bump.
    # dispatcher 3080→3120: _dispatch_is_duplicate caps Builder at ONE per
    # goal regardless of decision_id (two Builders prove-in-place into one
    # L_<slug>.lean → loser's stub-snapshot restore clobbers winner's proof;
    # P13 3502/4284/4288) — 2026-06-16 — conscious bump.
    # 3120→3150: librarian STALL log surfaces failure_detail by pipeline_id
    # (df77f05) + self-start gated on integrity_verified (446533a, classify-time
    # TOCTOU) — 2026-06-17 — conscious bump.
    # 3150→2200: #11 P2 — propagation cluster + cascade_one (~960 lines) moved
    # to state/transitions.py; ratchet down to lock the gain — 2026-06-22.
    # 2200→2240: reconcile pre-existing growth (harvest-fix `_harvest_outstanding`,
    # 1b2a6b5) that a prior push's ratchet missed — 2026-07-02 — conscious bump.
    # 2240→2270: BUG3 — sign-off pause checks in the 3 librarian dispatch paths
    # (selfstart / refill / harvest_outstanding) — 2026-07-03 — conscious bump.
    # 2270→2310: audit trigger derivation (_audit_due, v26) + consecutive-
    # strategist observability probe — 2026-07-11 — conscious bump.
    # 2310→2340: T1.5 audit seat-source enqueue (audit was derivation-only
    # and starved on busy problems / --once runs) — 2026-07-12 — conscious bump.
    # 2340→2400: periodic wakes outrank events (user ruling): _routine_due
    # derivation twin + since_iso clocks + reordered trigger ladder —
    # 2026-07-12 — conscious bump.
    "Tooling/core/dispatcher.py": 2400,
    # #11 — state-transition machine (canonical states, edge registry, checked
    # mutators, guard predicates, propagation cluster + cascade_one relocated
    # here in P2) — 2026-06-22.
    # 1300→1380 (2026-07-04): ProvedReceipt — the proved-flip soundness
    # boundary (receipt requirement + sanctioned-kind registry) enforced at
    # the transition chokepoint (arch-review task #2).
    # 1380→1400 (2026-07-04): v17 queue scope plumbing (_queue_problem_of)
    # rides the same file as the enqueue-adjacent cascade helpers.
    # 1400→1440 (2026-07-09): _maybe_review_goal_out_of_routes — park-last-
    # route escalation to T2 review (putnam_2025_b6 mutual-deadlock fix B);
    # belongs beside _maybe_stall_parent_strategies — conscious bump.
    # 1440→1470 (2026-07-12): predicted_batch_delta (FSM §2.3, the
    # stall-advance currency) — conscious bump.
    "Tooling/state/transitions.py": 1470,
    # 3100→3150: classify_cited_slug — shared citation-eligibility SoT for the
    # commit gate (_cite_gate) AND validate_file's pre-commit mirror (#8 / P2)
    # — 2026-06-17 — conscious bump.
    # 3150→3200: clear_librarian_fail_counts_for_problem — a fresh classify
    # drops stale per-attempt stall caps so a reverted+re-ingested problem does
    # not inherit a STALL (residue_thm) — 2026-06-17 — conscious bump.
    # 3200→3220: Phase 12 v12 migration block — kb_entries DROP COLUMN scope
    # (breadth reads off node_id alone) — 2026-06-27 — conscious bump.
    # 3220→3360: anchor+claim — is_deliverable column + mark_deliverable/
    # deliverables helpers + v13 `_migrate_to_phase13` table rebuild (MarkDeliverable
    # CHECK widening) — 2026-07-02 — conscious bump.
    # 3360→3390: anchor+claim Phase 3 — goal_by_slug + set_inject_outcome_detail
    # (asterism reject reverse cascade) — 2026-07-02 — conscious bump.
    # 3390→3510: anchor+claim Phase 4 — v14 `_migrate_to_phase14` (Ingest CHECK
    # widening) + ingest_signoff_pending helpers — 2026-07-02 — conscious bump.
    # 3510→3530: classify_cited_slug alias-chain resolution (bea22b4, cite-gate
    # resolves a proved alias to its canonical) — 2026-07-03 — conscious bump.
    # db 3530→3550: v15 additive-collapse migration stamp + policy comment
    # (task #10 — user_version made a complete schema description again;
    # the legacy blind-ALTER block frozen by its own ratchet) — conscious
    # bump.
    # db 3550→3700: Phase 6 — v16 `ingested_at` migration + problem terminal
    # helpers (set/get/all_problems_ingested) + shared alive-CTE fragments
    # (single-source root ∪ detached seed) — 2026-07-04 — conscious bump.
    # →3800 (2026-07-04): v17 queue contract — lease claim/complete/expire
    # + scoped pop/flush + payload-aware contains (arch-review task #3).
    # 3800→3950 (2026-07-05): v18 Library index in the DB — migration step
    # (INDEX.md backfill) + the bridge-marker / bridged-index / signature
    # helper family (task #4). db.py split is on the opportunistic list.
    # 3950→4010 (2026-07-05): v19 goals.kind CHECK widen ('inductive') —
    # `_migrate_to_v19` table rebuild with live-column INSERT (Forward
    # inductive support) — conscious bump.
    # 4010→4090 (2026-07-05): v20 'instance' + `_widen_goals_kind_check`
    # (the v19 rebuild generalized for future kind additions) — conscious
    # bump.
    # 4090→4130 (2026-07-06): v21 spawn_usage (frontend charter §5-2) —
    # conscious bump. db.py split stays a #11 順勢項 (next schema rework).
    # 4130→4200 (2026-07-06): v22 review snapshot + connect_readonly
    # (charter §5-4/§5-5) — conscious bump; the split pressure is real now.
    # 4200→4400 (2026-07-07): v23 Scholar/FetchPaper CHECK widens (three-
    # table rebuild) + problem_papers bindings (paper v2 D11/D13) +
    # release_own_leases (graceful-exit sweep) — conscious bump;
    # migrations-out-of-db.py split is the natural cut at the next
    # schema rework (#11).
    # 4400→4410 (2026-07-07): problem_settings DDL (frontmatter
    # dissolve) — table only; accessors live in state/settings.py.
    # 4410→4425 (2026-07-07): unbind_paper (papers-page uncheck — the
    # write pair of bind_paper).
    # 4425→3000 (2026-07-07): the ratchet fired at v24 (library_decls
    # docstring/src_line) and collected the debt this block called for —
    # migrations + user_version stepping split to db_migrations.py
    # (~1500 lines out). Next cut if growth resumes: helper-family split
    # (#11 opportunistic list).
    # 3000→3100 (2026-07-11): T2 wake-pump livelock fix — parameterized
    # frontier semantics (stall vs dispatch) + has_live_inflight_inject
    # narrowing + goal_reviewed_at_current_attempts (~90 lines) —
    # conscious bump; the helper-family split (#11) is now overdue.
    # 3100→3120: manifest_history table DDL (self-audit §3-1b) —
    # 2026-07-12 — conscious bump.
    "Tooling/state/db.py": 3120,
    # Born 2026-07-07 from the db.py split (v24): additive backfills +
    # user_version stepping. Grows by one block per schema version.
    # 1560→1660 (2026-07-08): v25 AttemptDisproof CHECK widen (feature D,
    # single-table rebuild) — conscious bump.
    # 1660→1720 (2026-07-11): v26 audit trigger_kind CHECK widen (same
    # rebuild block shape) — conscious bump.
    # 1720→1750 (2026-07-12): v28 user_file_history carryover — conscious
    # bump.
    "Tooling/state/db_migrations.py": 1750,
    "Tooling/quality/librarian/cleanup/__init__.py": 50,
    # 560→640: _all_warnings (Mathlib-PR zero-warning detector, broader than
    # polish's subset) + _collapse_redundant_variable_blocks (scope-safe dup
    # variable-block tidy) + _build_for_warnings (force the mathlib standard
    # linter set on, which `lake env lean` drops) — 2026-06-17 — conscious bump.
    # 640→700: warm-or-cold verify primitive (#35 Stage 1) — _verify_source +
    # _leanrun_from_verify route whole-file gates onto a held cleanup session's
    # claimed gateway slot (~4-5s) with cold `lake env lean` fallback; wired
    # through _lake_check / _build_file_copy_isolated — 2026-06-19 — conscious bump.
    # 700→760: #35 stage 2/3 — _build_with_output warm routing + warm
    # _typecheck_capturing_types (#check types from info diagnostics, shared
    # _extract_check_types core) — 2026-06-19 — conscious bump.
    # 760→790: diff_magnitude (cleanup-throughput observability, 09736b8)
    # — 2026-07-06 — conscious bump.
    "Tooling/quality/librarian/cleanup/_common.py": 790,
    # 300→350: audit rewritten onto the shared LSP edit-mode retry loop
    # (`run_with_session_retries`, like builder / migrate-hole-fill) — cold-seed
    # `audited.lean` + warm incremental + --resume, `_write_mcp_config` LSP, and
    # the fence/type-invariance/zero-warning gate split out as the pure
    # `_audit_gate`. (Replaces the reverted dc30d3e `_type_generalizes`
    # drop-unused-hypothesis relaxation — an unused binder is now `_`-prefixed,
    # not deleted, so the type gate stays strictly invariant.) — 2026-06-18.
    # 350→400: parse_fn reads the agent's session token and threads it to the
    # whole-file warnings gate so it verifies on the agent's warm claimed slot
    # (#35 stage 3; the #check type gate stays cold) — 2026-06-19 — conscious bump.
    # 400→440: C4-B — audit context surfaces cross-library leaf-name clashes
    # (Library/INDEX.md → _library_name_index) so the agent enforces the
    # no-collision rule inline — 2026-06-22 — conscious bump.
    "Tooling/quality/librarian/cleanup/audit.py": 440,
    # 250→325: precise imports computed MECHANICALLY (`_compute_min_imports` /
    # `_parse_missing_imports` / `_inject_import_bumps`, driving mathlib's
    # `#import_bumps`) instead of the LLM guessing + retrying — eliminates the
    # `import Mathlib` umbrella deterministically. Includes the umbrella-unneeded
    # path (`_remove_umbrella_import`): a file whose Mathlib deps are covered
    # transitively by its Library siblings drops the umbrella outright (#44;
    # BanachTarski caught sibling-importing files keeping it) — 2026-06-21.
    # 325→420: import-min degrade fix — `#import_bumps` runs with its own generous
    # budget (`_IMPORT_BUMPS_TIMEOUT_SEC`: cold + async-off, 240s silently timed
    # out → umbrella, the dominant cause of the residue 7-file debt), and a
    # candidate LADDER (`_import_candidates` / `_dir_precise_imports`: precise →
    # REMOVE → minImports∪dir-pool) broadens before degrading to the umbrella —
    # 2026-06-22 — conscious bump.
    "Tooling/quality/librarian/cleanup/decide.py": 420,
    # 250→340: file_cleanup_underscore_unused_hyps — mechanical `_`-prefix of
    # `unusedVariables`-flagged hypothesis binders (#37), so the audit agent
    # doesn't burn its 960s budget `_`-prefixing 12+ binders one LSP round-trip at
    # a time on big files — 2026-06-19 — conscious bump.
    # 340→380: _decl_line_spans — Defs-origin freeze skips frozen decls in the
    # location-based `_`-prefix pass (Defs decls must never be modified by
    # cleanup) — 2026-06-20 — conscious bump.
    # 380→540: file_cleanup_normalize_whitespace — mechanical clear of the
    # text-based mathlib style linters (linter.style.whitespace / .emptyLine)
    # that only fire on a real module build, so the audit agent otherwise burns
    # its 960s budget hand-fixing 100+ `(0:ℝ)`→`(0 : ℝ)` spacings (residue
    # HomotopyIntegral 141+4 → 3 audit timeouts) — 2026-06-20 — conscious bump.
    # 540→560: olean-safe restore (try/finally) so a failed detection build never
    # leaves the module's olean missing (regression that failed downstream
    # decide/audit) — 2026-06-20 — conscious bump.
    "Tooling/quality/librarian/cleanup/mechanical.py": 560,
    # 200→220: per-decl gate + agent seed reproduce the file's `open …` lines
    # (`_opens_in`) so a proof referencing an opened symbol (`residue`) resolves
    # in the isolation probe instead of failing as an autoImplicit — 2026-06-20.
    "Tooling/quality/librarian/cleanup/simplify.py": 220,
}


def _line_count(rel: str) -> int:
    return len((ROOT / rel).read_text(encoding="utf-8").splitlines())


def test_files_stay_under_watermark() -> None:
    over = []
    for rel, limit in _WATERMARKS.items():
        n = _line_count(rel)
        if n > limit:
            over.append(f"{rel}: {n} lines > watermark {limit}")
    assert not over, (
        "file(s) grew past their size watermark — split the file or "
        "consciously bump the limit in this test:\n" + "\n".join(over))


def test_every_cleanup_module_has_a_watermark() -> None:
    # A new cleanup/*.py must be registered here (with its own watermark),
    # so stage modules can't grow unwatched.
    cleanup_dir = ROOT / "Tooling" / "quality" / "librarian" / "cleanup"
    unlisted = sorted(
        f"Tooling/quality/librarian/cleanup/{p.name}"
        for p in cleanup_dir.glob("*.py")
        if f"Tooling/quality/librarian/cleanup/{p.name}" not in _WATERMARKS)
    assert not unlisted, f"add a watermark for: {unlisted}"
