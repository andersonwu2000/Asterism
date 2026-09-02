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
    # 440→450 / 1170→1190 (2026-07-30): the metaprogramming gate reaches
    # the Library arm — agent Lean assembled into a Library file and built
    # by lake was the one un-scanned elaboration path. Conscious bump.
    "Tooling/pipeline/librarian/gate.py": 450,
    "Tooling/pipeline/librarian/context.py": 430,
    "Tooling/pipeline/librarian/execute.py": 1190,  # +universe hoist/dedup (#72)
    "Tooling/pipeline/librarian/bridge.py": 390,
    # 560→570 (2026-08-13): harvest seeds scope to the top group —
    # the Library is curated for people, so what enters it is what the
    # top group promoted (user ruling). Conscious bump.
    "Tooling/pipeline/librarian/run.py": 570,
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
    # 2400→2420 (2026-07-12): FSM P3 wake-legality guards at the four
    # seat sources — conscious bump.
    # 2420→2490 (2026-07-14): quota-wait wiring (user: sleep to resets_at
    # instead of exiting) — breaker consult, rc=126 escalation, refill/pop
    # gate, budget-clock pause; the behavior itself lives in
    # core/quota_wait.py — conscious bump.
    # 2490→2510 (2026-07-18): config drift joins the code-drift handoff
    # (settings apply to a live run via graceful handoff) — conscious
    # bump; the fingerprints themselves live in lsp/lifecycle.py.
    # 2510→2520 (2026-07-19): dispatcher pool applies the gateway's
    # ram_clamped_pool formula (over-dispatch vs clamped slots read as
    # gateway death) — conscious bump.
    # 2520→2600 (2026-08-02): v35 per-group Strategist seat —
    # `_enqueue_strategist` (the one row shape), `_strategist_target`
    # (group→problem resolution incl. legacy rows) and the per-tick
    # top-group self-heal. Conscious bump.
    # 2600→2660 (2026-08-04): #158 — scope_mismatch_reason pre-flight +
    # the in-run authoritative twin (a scope matching no registered
    # problem must refuse loudly, not idle forever). Conscious bump.
    # 2660→2720 (2026-08-07): the per-(provider, model) quota ledger —
    # seat resolution, the per-tick hold, and feeding an rc=126 spawn
    # back into the ledger (the only quota channel a provider without a
    # usage API has). The judgement itself lives in `core/quota.py`;
    # what landed here is wiring. Conscious bump.
    # 2720→2740 (2026-08-07): the seat/queue spelling fix the first
    # wiring needed (production found it in an hour) plus consuming
    # agy's own reset time. Conscious bump.
    # 2740→2760 (2026-08-08): memory-exhaustion classification in
    # `_classify_worker_exception` (WinError 1455 burned ten attempts
    # with no dead_attempts row) + the `system_killed` dead-attempt
    # exemption. Conscious bump.
    # 2760→2800 (2026-08-08): the consecutive-unclassified breaker —
    # unknown spawn deaths stopped charging goal attempts, so nothing
    # else would ever halt a goal dying the same unexplained way, and
    # the escalation goes to the operator rather than the Strategist.
    # Conscious bump.
    # 2800→2830 (2026-08-13): the breaker learned a third answer. "The
    # usage endpoint did not respond" was being spent as "the endpoint
    # says quota is healthy", so four failed probes convicted claude.exe
    # and exited the daemon while another thread parked to that same
    # window's real reset. Plus the pop loop finally reading the
    # per-target cooldown it had been setting all along — without it,
    # ten fast-fails arrived in 51 seconds and outran the quota ledger's
    # own cache. Conscious bump.
    # 2830→2865 (2026-08-13): ledger sovereignty. `sync_quota_holds` and
    # `SchedulerState.quota_cooldown_kind` are GONE — the quota fact is
    # asked of `core.quota` each tick instead of mirrored here, so the
    # release path that held the Strategist for eight hours (08-11) has
    # no state left to get wrong. Net across `Tooling/core` is smaller;
    # this file keeps the incident's explanation plus the rc=126 brake
    # that stayed. The two helpers that could live elsewhere already
    # did move (`admission`, `quota.report_block_changes`). Conscious
    # bump.
    # 2865→2868 (2026-08-13): both `maybe_enter` call sites state their
    # evidence class (`trigger_quota_classified`) so a non-quota trip
    # that parks on a confirmed window indicts the stale markers out
    # loud instead of being covered by the endpoint. Conscious bump.
    # 2868→2875 (2026-08-14): the gateway liveness gate (#203) — ask
    # `/health` before buying another spawn against a gateway a spawn
    # already reported unreachable. The ratchet did its job here: the
    # feature arrived +87 and the whole concern moved out to
    # `core/gateway_health.py`, which also let the warm-failure and
    # held-gateway endings become ONE exit instead of two blocks doing
    # the same three things. +7 is what is left: the scheduler-state
    # field, the derived grace constant, and the policy wrapper that
    # keeps the numbers and the only run-ending call in this file.
    # Conscious bump.
    # 2875→2893 (2026-08-14): the bounded self-heal (#203, owner ruling)
    # — one relaunch of a gateway that died, credit earned back by a
    # finished pipeline or by outliving `dispatch.spawn_timeout_sec`.
    # The decision and the relaunch are `gateway_health.resolve_fatal`'s;
    # what lands here is the state field, the config read for that window
    # (a fourth number, so it goes with the other numbers), the
    # success-branch line that returns the credit, and the two-line
    # widening of the exit block. Conscious bump.
    # 2893→2914 (2026-08-14): the door learns that a TERMINAL GROUP holds
    # no seat. `groups_needing_t1` has filtered the periodic clock on
    # `active` since v35 and the event relay never learned it, so groups
    # 383 and 381 each ran two batches on charters they had already
    # delivered. The check goes at the pop-loop door because that is the
    # one place every dispatch passes; anywhere else needs a copy per
    # enqueuer, which is the shape this day was spent removing.
    # Conscious bump.
    # 08-18 +27: the provider_network branch + network-wait gates
    # (`core/network_wait` holds the behavior; this is the wiring).
    # 2941→2950 (2026-08-19): the stale door generalizes — Goal rows
    # (Formalizer/Builder) whose goal settled between enqueue and pop
    # drop at the same one-place-every-dispatch-passes check that
    # already held the terminal-group fact. Conscious bump.
    # 2026-08-25: +50 — the RAM ledger's split admission (Lean gates on
    # gateway open slots, NL on measured RAM; owner design). The pure
    # ledger lives in core/ram_ledger.py; only the admission seam is
    # here. Conscious bump.
    # dispatcher.py split move-only into core/dispatcher/ (B4, 2026-08-29);
    # fresh locks per module — the monolith never grows back.
    "Tooling/core/dispatcher/__init__.py": 250,
    "Tooling/core/dispatcher/refill.py": 300,
    "Tooling/core/dispatcher/triggers.py": 632,  # 2026-08-31 bench seat guard  # +18 2026-08-31 active-group seat guard + moot-verdict extinguish  # +suppress_stall (promotion gate) 2026-08-30
    "Tooling/core/dispatcher/worker.py": 650,
    "Tooling/core/dispatcher/lock.py": 300,
    "Tooling/core/dispatcher/loop.py": 1320,  # +16 2026-09-02 HID §3.3: the tick applies the human command queue (state/commands.apply_pending, guarded)
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
    # 1470→1530 (2026-07-12): problem FSM P2 — PROBLEM_STATES/EDGES +
    # apply_problem_transition — conscious bump.
    # 1530→1580 (2026-07-12): FSM P3 — WAKE_LEGALITY matrix +
    # problem_accepts_wake — conscious bump.
    # 1620 → 1660 (2026-07-30): promise-aware aliveness in
    # `_maybe_stall_parent_strategies` — the b6_1 four-level review
    # cascade. The two helpers are 30 lines of code and a long WHY
    # (the incident + why the anti-stranding guarantee survives);
    # the reasoning belongs next to the predicate it justifies.
    # 1660→1700 (2026-08-02): v35 — a review wakes the group that owns
    # the goal, not the problem. Conscious bump.
    # +10, 2026-08-02: GROUP_EDGES + its three event labels. The fourth
    # entity's transition law belongs beside the other three — splitting it
    # out would put one FSM somewhere no reader of this module would look.
    # 1710→1740 (2026-08-04): poison-queue-row guard — `_queue_problem_of`
    # Group branch + both infra-retry call sites skip-loudly on an
    # unresolvable problem (the 08-03 SLC silent-stall class). Conscious
    # bump.
    # 1740→1750 (2026-08-06): 'Delegate' joins the promise-carrier set in
    # `_awaiting_promised_batch` (v35 seam — a park waiting on a
    # sub-group escalated the root to review). Conscious bump.
    # 1750→1755 (2026-08-13): GOAL_FAILED_TERMINALS derived view — the
    # {"disproved","dead"} predicate was hand-copied in four modules;
    # its declaration belongs in the vocabulary's home. Conscious bump.
    # 1755→1776 (2026-08-14): `NON_IDEMPOTENT_SELF` — a self-edge is
    # idempotent only when arriving is not itself the event. Reaching a
    # terminal GROUP status notifies the parent, so a second arrival
    # notifies twice; `_check` had been waving every `frm == to` past the
    # table that says this is the one thing it exists to forbid.
    # Conscious bump.
    # 1776→1780: the descendant edge for the group cascade — a retired
    # charter now retires the sub-projects it delegated, and a new edge
    # needs its event label registered here. 2026-08-16. Conscious bump.
    # 1780→1810: `park_group_anchor` — the anchor-shelve of a closing
    # group, moved out of `_commit_close_group` into one verb so the
    # ancestor cascade and the startup sweep park anchors too (#223).
    # 2026-08-17. Conscious bump.
    # 08-18 +15: the recovery event labels + the disproved revival edge
    # and its incident documentation (claimed-counterexample park).
    # 08-25 +5: v44 minted-only hard-terminal walk rationale (cited
    # consumers must not block Reopen on shared goals).
    # 08-25 +41: cited-wait conduction (`_review_cited_waiters` — a
    # shelve returns citing waiters to their group's review at once).
    "Tooling/state/transitions.py": 1935,  # +21 2026-09-02 HID §1.3: the shelve cascade splits into a read half (`shelve_cascade_targets`, what the confirm window names) and a write half  # +5 2026-08-30 problem terminal `refuted`  # +7 2026-09-02 v48 HID §3.2: a human ConfirmShelve is never a live promise (_awaiting_promised_batch)
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
    # 3120→3150 (2026-07-12): problem_quiet extraction (FSM P3, the
    # named quiet guard) — conscious bump.
    # 3150→3180 (2026-07-18): produced_kind attribution setter
    # branch + superseded outcome split — conscious bump.
    # 3180→3220 (2026-07-18): _strategy_death_detail (dead-redispatch
    # WHY synthesized into outcome_detail; the Forward-decline parity
    # fix) — conscious bump.
    # 3220→3420 (2026-08-02): v35 discussion groups — the `groups` DDL,
    # the two group pointers on strategist_decisions, 'Group' in the two
    # target_kind CHECKs, and the batch machinery's third artifact
    # (`BATCH_DECISION_KINDS` + `propagate_inject_outcome_from_group` +
    # the group arm of `has_active_inflight_inject`). The store's
    # accessors live in state/groups.py rather than here — the parts that
    # stayed are the ones that belong beside the batch predicates they
    # extend. Conscious bump.
    # 3420→3540 (2026-08-02): v35 per-group Strategist seat —
    # `groups_needing_t1` / `group_routine_due` (the clock moves to the
    # group) and the group arm of the anti-idle predicate. Conscious bump.
    # 3540→3660 (2026-08-02): v35 group-scoped stall — `is_group_stalled`
    # + `_group_quiet` + `groups_stalled`, and the authoring-group clause
    # the two in-flight predicates share. Conscious bump.
    # 3660→3670 (2026-08-03): waiting-parent routine freeze — the
    # active-children NOT EXISTS clause in `groups_needing_t1` and its
    # freeze-semantics docstring (operator ruling). Conscious bump.
    # 3670→3680 (2026-08-04): `is_in_queue` poison-row exclusion (the
    # 08-03 stall class, dedup edge). Conscious bump.
    # 3680→3740 (2026-08-07): v36 `goal_events` — the table DDL plus the
    # append inside `update_goal_status`, which is now the sink that
    # records every goal transition (the frontend's Timeline cannot read
    # `updated_at` as an event clock). Conscious bump.
    # 3740→3790 (2026-08-08): v38 pipelines-lifetime rows —
    # `record_pipeline_start` / `finish_pipeline` replace the single
    # INSERT-at-completion `record_pipeline`, plus the SCHEMA comment
    # documenting why the row must exist from dispatch (eager
    # dead_attempts, the goal-7486 drift class). Conscious bump.
    # 3790→3805 (2026-08-13): `unclaim_queue_row` — "not yet" as
    # distinct from "never". Every other pop-loop skip deletes the row
    # on the reasoning that refill re-derives it, which is false for the
    # rows a retry path enqueued directly; a cooling one is put back
    # instead. Conscious bump.
    # 3805→3840 (2026-08-13): `top_group_id` — one home for
    # `parent_group_id IS NULL`, which was spelled inline in four
    # places — plus the `deliverables` docstring finally naming WHICH
    # callers may scope. The old text read as an unconditional
    # instruction and following it everywhere would have cut 21 proved
    # bricks out of harvest. Conscious bump.
    # 3840→3855: a delivery's batch-done wake is redirected to the
    # nearest ACTIVE ancestor. Addressed verbatim, it named a parent that
    # had already left, and the dispatcher drops a Strategist row whose
    # group is terminal — so the child's delivery reached nobody
    # (2026-08-16). Conscious bump.
    # 3855→3870 (2026-08-19): v40 Manifest retirement — `problems` DDL
    # loses manifest_path / gains user_word, and the SCHEMA comments
    # explaining the DB-resident intent pair. Conscious bump.
    # 3880→3900 (2026-08-25): v44 strategy_subgoals.link_kind — DDL
    # provenance comment (which readers traverse which edge kind) +
    # link_subgoal param. Conscious bump.
    # 3930→(retired) (2026-08-29): move-only split into `Tooling/state/db/`
    # — the #11 順勢項 this whole history called for, finally landed. Same
    # section cuts as the SoT comments above (core/paths/goals/problems/
    # reach/strategies/pipelines/queue/deaths/library); facade re-exports
    # every symbol so `db.X` call sites are unaffected. See the born-
    # 2026-08-29 entries below.
    "Tooling/state/db/__init__.py": 200,  # born 2026-08-29 from the db.py split
    "Tooling/state/db/core.py": 970,  # +62 2026-09-02 HID §1.4: `scope_sql`/`scope_names`/`scope_matches` — a scope may name an explicit list, and the translation to SQL lives in ONE place  # born 2026-08-29 from the db.py split
    "Tooling/state/db/paths.py": 150,  # born 2026-08-29 from the db.py split
    "Tooling/state/db/goals.py": 650,  # born 2026-08-29 from the db.py split
    "Tooling/state/db/problems.py": 1200,  # born 2026-08-29 from the db.py split
    "Tooling/state/db/reach.py": 200,  # born 2026-08-29 from the db.py split
    "Tooling/state/db/strategies.py": 400,  # born 2026-08-29 from the db.py split
    "Tooling/state/db/pipelines.py": 165,  # born 2026-08-29 from the db.py split  # +routine audit 2026-08-30
    "Tooling/state/db/queue.py": 250,  # born 2026-08-29 from the db.py split
    "Tooling/state/db/deaths.py": 100,  # born 2026-08-29 from the db.py split
    "Tooling/state/db/library.py": 300,  # born 2026-08-29 from the db.py split
    # Born 2026-07-07 from the db.py split (v24): additive backfills +
    # user_version stepping. Grows by one block per schema version.
    # 1560→1660 (2026-07-08): v25 AttemptDisproof CHECK widen (feature D,
    # single-table rebuild) — conscious bump.
    # 1660→1720 (2026-07-11): v26 audit trigger_kind CHECK widen (same
    # rebuild block shape) — conscious bump.
    # 1720→1750 (2026-07-12): v28 user_file_history carryover — conscious
    # bump.
    # 1750→1780 (2026-07-12): v29 problem-state backfill — conscious bump.
    # 1780→1800 (2026-07-17): v30 programme_revisions (research mode) —
    # conscious bump; the migration chain grows by design per version.
    # 1800→1815 (2026-07-18): v31 passed-rev partial unique index —
    # conscious bump.
    # 1815→1840 (2026-07-18): v32 produced_kind attribution column —
    # conscious bump.
    # 1950→2220 (2026-08-02): v35 discussion groups — three CHECK
    # widenings (each a rebuild-and-copy, since SQLite cannot alter a
    # CHECK in place) plus the top-group backfill. The chain grows by one
    # block per schema version by design — conscious bump.
    # 2220→2260 (2026-08-07): v36 `goal_events` — one additive block
    # (table + two indexes, no rebuild, no backfill). Conscious bump.
    # 2260→2340 (2026-08-08): v38 pipelines rebuild — status CHECK gains
    # 'running', outcome/finished_at go NULLable (rebuild-and-copy; the
    # chain grows by one block per schema version by design). Conscious
    # bump.
    # 2340→2490 (2026-08-19): v39+v40 blocks — v40 is the Manifest
    # retirement rebuild (top-group charter backfill from a still-on-disk
    # legacy Manifest.md, problem_settings seeding, manifest_path DROP).
    # The chain grows by one block per schema version by design.
    # Conscious bump.
    # 2710→2750 (2026-08-25): +v44 link_kind block (grows by one block
    # per schema version by design). Prior: +migration file-mutex & v43
    # self-heal (2026-08-24); +v43 stall rebuild.
    # 2750→2800: judge provenance columns (survey P1/P2,
    # 2026-08-29) — conscious bump.
    # 2874→3020: v48 (2026-09-02, human_interface_design §3.1-§3.4) — the
    # `projects` / `human_commands` DDL, the Project backfill and the
    # strategist_decisions rebuild for `actor` all live in the ladder by
    # design (a SCHEMA-declared column would order differently on a fresh
    # DB than on a migrated one) — conscious bump.
    "Tooling/state/db_migrations.py": 3020,  # 2026-08-31 v47 benched  # +1 2026-08-30 last_words column  # +39 2026-08-30 v46 problems.state CHECK gains 'refuted'  # +routine audit 2026-08-30
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
    # The LSP gateway. `gateway.py` (5,890 lines, never watched here) became
    # `Tooling/lsp/gateway/` on 2026-08-29 — move-only, first batch of four
    # axes out of the monolith (state / elab / backend / weigh); the facade
    # __init__ still holds governor, sessions, leantext, rpc, gates, verify
    # and the HTTP surface, which later batches carry out. Every entry is
    # the file's line count at that split, rounded up to the next 50 — the
    # __init__ number is meant to keep FALLING as the remaining axes leave.
    # 5250→4250: the RAM governor left for `governor.py` (A1-2) — pressure
    # outlet, weight cap, wedge/heavy recycle, shed, mid-lease rewarm,
    # freeze/thaw, converger. Sessions, leantext, rpc, gates, verify and
    # health are still to come.
    # 4250→3650: session lifecycle (`sessions.py` — borrow order, acquire,
    # register/release, stale-claim sweep) and the /health payload plus its
    # governor-refreshed snapshot (`health.py`) left (A1-3). The HTTP routes
    # stayed. leantext, rpc, gates and verify are still to come.
    # 3650→2200: the Lean-text axis (`leantext.py` — compilation unit,
    # sibling stubs, line_map, diag remap, resync) and the four in-spawn MCP
    # tools (`rpc.py`), with the FastMCP instance and `_offload_to_thread`
    # in a small `server.py` so the tool decorators resolve before the
    # facade finishes executing (A1-4a). Gates, verify and the HTTP surface
    # are what remain for 4b.
    # sessions 650→600: `_echo_removed` + `_ECHO_END_CHARS` moved on to
    # `rpc.py`, whose `apply_edit` is their only consumer (A1-4a).
    # state 250→300: `_log_for` and `_ts_now` landed here (A1-4a) — two
    # dependency-free leaves that let sessions' call-time reach-backs close.
    # 2200→1050: the commit-gate mirrors (`gates.py` — citation,
    # annotation, locked signature, stale olean, slug collision, decl
    # head, namespace, axioms) and the candidate probe with the two
    # /verify sync cores (`verify.py` — `validate_file`,
    # `_verify_sync`, `_verify_session_sync`) left (A1-4b). What remains
    # IS the HTTP surface — eleven `@mcp.custom_route` handlers, the
    # session-header middleware, `main()` and the facade — so this
    # number stops falling here.
    "Tooling/lsp/gateway/__init__.py": 1113,  # born 2026-08-29 from the gateway split (A1-1); +2 2026-08-30 stderr stamp install; +49 2026-08-30 build-lease routes (one CPU budget, two consumers); +3 2026-08-30 release routes off the event loop
    "Tooling/lsp/gateway/state.py": 300,  # born 2026-08-29 from the gateway split (A1-1)
    "Tooling/lsp/gateway/elab.py": 320,  # born 2026-08-29 from the gateway split (A1-1); +65 2026-08-30 build leases — the second tenant lives beside the semaphore it borrows from
    "Tooling/lsp/gateway/backend.py": 250,  # born 2026-08-29 from the gateway split (A1-1)
    "Tooling/lsp/gateway/weigh.py": 150,  # born 2026-08-29 from the gateway split (A1-1)
    "Tooling/lsp/gateway/governor.py": 1100,  # born 2026-08-29 from the gateway split (A1-2)
    "Tooling/lsp/gateway/sessions.py": 600,  # born 2026-08-29 from the gateway split (A1-3)
    "Tooling/lsp/gateway/health.py": 150,  # born 2026-08-29 from the gateway split (A1-3)
    "Tooling/lsp/gateway/leantext.py": 800,  # born 2026-08-29 from the gateway split (A1-4a)
    "Tooling/lsp/gateway/rpc.py": 950,  # 2026-08-29 wall (CPU-second meter) + native_decide gate; SPLIT before the next bump (gates/wall -> own module)
    "Tooling/lsp/gateway/server.py": 100,  # born 2026-08-29 from the gateway split (A1-4a)
    "Tooling/lsp/gateway/gates.py": 500,  # 2026-08-30 ancestor-cycle refusal at the editing tools
    "Tooling/lsp/gateway/verify.py": 880,  # +30 2026-08-31: #5 conditional headline hoist
    "Tooling/lsp/gateway/__main__.py": 50,  # born 2026-08-29 from the gateway split (A1-1)
    # `Tooling/core/cli.py` (3,307 lines, no prior watermark here) split
    # move-only into `Tooling/core/cli/` by command domain (task A3): the
    # facade `__init__.py` re-exports every public (and tested private)
    # symbol; `run.py` is the daemon/run lifecycle (cmd_run, daemon_status/
    # start/stop, cmd_daemon, cmd_serve); `problems.py` is init/init-batch/
    # reset + the init_problem/delete_problem/wipe_problem_rows
    # chokepoints; `diagnose.py` is the health-check surfaces (status/
    # doctor/library-verify/review/regress/knowledge-stats/drift-check/
    # logs/config); `maint.py` is the remaining operational commands
    # (reject/approve-ingest/reject-ingest/repin/charter/word/revive/
    # library-backfill-declinfo/prune/paper-add/paper-index/kb-migrate);
    # `main.py` is the argparse wiring; `__main__.py` preserves
    # `python -m Tooling.core.cli` (daemon_start's own relaunch argv, the
    # systemd unit, installer/launch.ps1).
    "Tooling/core/cli/__init__.py": 150,  # born 2026-08-28 from the cli.py split (A3)
    "Tooling/core/cli/__main__.py": 50,  # born 2026-08-28 from the cli.py split (A3)
    "Tooling/core/cli/run.py": 764,  # +6 2026-09-02 promotion_builds — the promotion gate is a thread, invisible to in_flight (HID §3.4)  # +8 2026-08-31 in_flight=running pipelines, leases separate  # born 2026-08-28 from the cli.py split (A3)
    "Tooling/core/cli/problems.py": 950,  # born 2026-08-28 from the cli.py split (A3)
    "Tooling/core/cli/diagnose.py": 850,  # born 2026-08-28 from the cli.py split (A3)
    "Tooling/core/cli/maint.py": 582,  # 2026-08-31 bench/unbench commands  # born 2026-08-28 from the cli.py split (A3)
    "Tooling/core/cli/main.py": 380,  # +3 2026-09-02 --scope help names the explicit-list form (HID §1.4)  # +3 2026-09-01: serve --host flag  # 2026-08-31 bench/unbench parsers  # +10 2026-08-30 catalog-verify subcommand  # born 2026-08-28 from the cli.py split (A3)
    # `Tooling/pipeline/strategist.py` (3,078 lines, no prior watermark
    # here) split move-only into `Tooling/pipeline/strategist/` by
    # pipeline stage (Phase B, task B1): `model.py` is the Decision
    # dataclass + decision-kind vocabulary + decision.json parser;
    # `verify.py` is the self_verify stage (verify_decision/
    # verify_decisions) plus USER_AMEND_FILES; `commit.py` is the commit
    # stage (CommitOutcome + every _commit_* handler); `wake.py` is the
    # outer run_strategist entry, the proposal-package gate, and the
    # Adversary revision loop's mechanical delta gate. Facade
    # `__init__.py` re-exports every public (and tested private) symbol.
    "Tooling/pipeline/strategist/__init__.py": 100,  # born 2026-08-28 from the strategist.py split (B1)
    "Tooling/pipeline/strategist/model.py": 300,  # born 2026-08-28 from the strategist.py split (B1)
    "Tooling/pipeline/strategist/verify.py": 1118,  # +9 2026-08-30 two-part brick shape gate on Inject proof  # +17 2026-08-30 refuted needs the gate-born brick; Ingest accepts a disproved root  # born 2026-08-28 from the strategist.py split (B1)  # +routine audit 2026-08-30; +7 2026-08-30 action gate reads target_id, shelved roots not in flight (3e61beb9 shipped red here — caught 05:59Z)
    "Tooling/pipeline/strategist/commit.py": 1055,  # +39 2026-09-02 HID §3.2/§3.3: `actor` threaded through every INSERT + the human Inject's dispatch band  # +11 2026-08-30 Ingest on a disproved root closes as refuted  # born 2026-08-28 from the strategist.py split (B1)
    "Tooling/pipeline/strategist/wake.py": 906,  # +6 2026-08-30 last-words turn before the adversarial discard  # born 2026-08-28 from the strategist.py split (B1)
    # `Tooling/agent/phase2_context.py` (2,428 lines, no prior watermark
    # here) split move-only into `Tooling/agent/phase2_context/` along the
    # file's own section breaks (task B2): `dossier.py` is the pending-
    # review dossier (failure/adjudications/strategies/ancestor-chain
    # sections); `outcomes.py` is the Inject-batch results (delegate/
    # delivered-group summaries, the per-step scoreboard + BATCHES.md,
    # `_prose_label`, worker declines, pending reopens — `pipeline/
    # adversary.py` imports `_section_inject_batch_outcomes` from this
    # package directly, not through the facade); `compile.py` is the rest
    # of the Strategist side (trigger/gate/stall sections, roster/replay/
    # plan/directive/tree/charter, `compile_strategist_context` itself,
    # `_CATALOG_RECENT_N`); `forward.py` is the Forward side (brief/
    # library/history/Programme-proof/presearch/conventions,
    # `compile_forward_context` itself). Facade `__init__.py` re-exports
    # every public (and tested private) symbol.
    "Tooling/agent/phase2_context/__init__.py": 150,  # born 2026-08-28 from the phase2_context.py split (B2)
    "Tooling/agent/phase2_context/dossier.py": 250,  # born 2026-08-28 from the phase2_context.py split (B2)
    "Tooling/agent/phase2_context/outcomes.py": 850,  # born 2026-08-28 from the phase2_context.py split (B2)
    "Tooling/agent/phase2_context/compile.py": 1243,  # +31 2026-08-31 heading demotion + wake-time TREE refresh  # +5 2026-08-30 the author's last words after the rebuttal  # +1 2026-08-30 refuted names the gate brick  # +41 2026-08-30 rebuttal surface after a discarded cycle (last round inline, REJECTED.md lazy)  # born 2026-08-28 from the phase2_context.py split (B2)  # +routine audit 2026-08-30
    "Tooling/agent/phase2_context/forward.py": 350,  # born 2026-08-28 from the phase2_context.py split (B2)
    # `Tooling/serve/data.py` (2,357 lines, no prior watermark here) split
    # move-only into `Tooling/serve/data/` along the file's own section
    # breaks (task B3): `status.py` is the status-chip derivation shared
    # by board()/problem_detail(); `edges.py` is citation-edge extraction
    # + `problem_detail` itself; `timeline.py` is the Timeline event log
    # plus everything downstream of that section marker (Programme reads,
    # the group tree, goal/strategy detail, inbox/review/library-index) —
    # the Programme-read cluster (`programme`/`_programme_events`/
    # `_programme_rev`/`_group_clause`) moved here from its literal
    # position ahead of the "Timeline" marker, because it and the
    # groups-tree cluster it calls were consumed by both `edges.py`'s
    # `problem_detail` and this module's own `problem_events`/
    # `_decision_events` — a straight line-range split would have made
    # `edges.py` and `timeline.py` import each other; `library.py` is the
    # Library chapter (bridged-module parsing) plus the trailing
    # telemetry/papers/file-read leaves that share no call edge with it.
    # Facade `__init__.py` re-exports every public (and tested private)
    # symbol; `_link_kind_expr` stays in the facade itself as the one
    # helper both `edges.py` and `timeline.py` call.
    "Tooling/serve/data/__init__.py": 200,  # born 2026-08-28 from the data.py split (B3)
    "Tooling/serve/data/status.py": 200,  # born 2026-08-28 from the data.py split (B3)
    "Tooling/serve/data/edges.py": 550,  # born 2026-08-28 from the data.py split (B3)
    "Tooling/serve/data/timeline.py": 1250,  # born 2026-08-28 from the data.py split (B3)
    "Tooling/serve/data/library.py": 500,  # born 2026-08-28 from the data.py split (B3)
    "Tooling/serve/data/verdict.py": 100,  # born 2026-08-29 — one revision's judge verdict
    # ── 2026-08-29 default-cap sweep ─────────────────────────────────
    # The ratchet used to be an OPT-IN list: gateway.py reached 5,886
    # lines and cli.py 3,307 with no entry at all, because nobody had
    # ever added one. The default cap below closes that hole; these are
    # the files that were already over it, grandfathered at their
    # current size (next multiple of 50) — shrink-only, like the rest.
    "Tooling/pipeline/backward.py": 2370,  # +20 2026-08-30 certified negation lands as <slug>_disproof
    "Tooling/quality/dedupe.py": 1950,
    "Tooling/llm/zen_shim.py": 1950,
    "Tooling/llm/claude_cli.py": 1900,
    "Tooling/agent/context.py": 1815,  # +4 2026-08-30 intake counterexample section (the disproof turn)  # +8 2026-09-02 v48 HID §3.2: ADJUDICATIONS.md names a human ruling as the human's, not the filing group's
    # 1700→1750 (2026-08-29): one route, `/api/problems/{p}/programme/
    # verdict/{rev_id}` — the console's on-demand read of a revision's
    # judge verdict. app.py IS the route table, so an endpoint costs it
    # ~20 lines by construction; the read itself went to its own module
    # (`serve/data/verdict.py`) rather than into `timeline.py`, which
    # this same run would otherwise have pushed over its watermark.
    "Tooling/serve/app.py": 1750,
    "Tooling/knowledge/workspace_query.py": 1475,  # +25 2026-08-31 decl problem scoping + .lake workspace anchor; the 08-29 split promise still stands  # +20 2026-08-31 decl problem scoping + .lake workspace anchor; the 08-29 split promise still stands  # 2026-08-29 outline roster + defer-by-name + decl gNNNN (+41); next growth = split, not a bump
    "Tooling/pipeline/_retry.py": 1300,
    "Tooling/llm/codex_cli.py": 1250,
    "Tooling/pipeline/forward.py": 1200,
    "Tooling/lsp/lifecycle.py": 1160,  # 2026-08-30 wall-aware verify client timeout; SPLIT before the next bump
    "Tooling/llm/antigravity_cli.py": 1150,
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

# Any module NOT in the watermark list must stay under this. The list
# above is the conscious-exception mechanism: a file that legitimately
# needs more space gets a named entry (visible in review), it does not
# get to grow in silence — that is exactly how gateway.py reached 5,886
# lines unwatched (split A1, 2026-08-29).
_DEFAULT_CAP = 1000


def test_unlisted_modules_stay_under_the_default_cap() -> None:
    over = []
    for p in (ROOT / "Tooling").rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel in _WATERMARKS:
            continue
        n = sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
        if n > _DEFAULT_CAP:
            over.append(f"{rel}: {n} > {_DEFAULT_CAP}")
    assert not over, (
        "unlisted module(s) over the default cap — split the file, or "
        "add a conscious watermark entry in the same PR so the growth "
        "is visible in review:\n" + "\n".join(over))
