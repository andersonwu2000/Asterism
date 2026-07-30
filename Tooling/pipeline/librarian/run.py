"""librarian.run — split out of the former pipeline/librarian.py monolith."""
from __future__ import annotations

from pathlib import Path as _Path
from ...state import db

from ._base import WORK_KINDS
from .classify import _decl_line_counts, _plan_usage_and_canon, _reorder_decls_by_intrafile_refs, _root_source, commit_classify, parse_classify, verify_classify, verify_merged_file_sizes
from . import bridge
from .context import compile_librarian_context
from .execute import _run_migrate


def run_librarian(conn, *, problem: str, work_kind: str,
                  workspace, pipeline_id: str,
                  target: str | None = None,
                  whitelist: "list[str] | None" = None):
    """Outer Librarian entry. Returns PipelineResult.

    `work_kind` selects the prompt (prompts/librarian/<kind>.md) and the
    commit path. `target` is required for migrate — the Library FILE to
    write (per-file is the parallel unit, plan §5 Step 3). `whitelist` is
    the problem's authorized axiom set (Manifest `axioms_whitelist`, or the
    framework default) — threaded to the migrate commit gate's per-file
    axiom check; only the migrate kind uses it."""
    from .. import PipelineResult, PROMPT_DIR
    from ... import agent

    # v0.3 (plan §0/§3): dedup is no longer an agentic keep/drop judgment —
    # it is a mechanical "inventory + keep everything" step (no spawn, no
    # prompt). Keeping all decls is precisely what lets migrate be mechanical
    # (every proof-term reference resolves to a kept sibling → no holes → no
    # LLM). Routed before the prompt-path guard.
    if work_kind == "dedup":
        return _run_keepall(conn, problem=problem, workspace=workspace)

    # v0.4 (plan §10/§11, §13): cleanup runs the dedup-audit engine on the
    # migrated (staging) Library — drop/merge/bridge, each isolate-gated,
    # bridge's Gate B the final backstop. Like dedup it owns its prompts/spawns
    # → routed before the prompt-path guard. `target` is the per-file unit
    # (§13 3c-2); None = whole-problem serial pass.
    if work_kind == "cleanup":
        return _run_cleanup(conn, problem=problem, workspace=workspace,
                            target_file=target, pipeline_id=pipeline_id,
                            whitelist=whitelist)

    # v0.3 mechanical Gate B (plan §2 定海神針): `_run_bridge` is a no-agent,
    # no-prompt probe (its attempts_dir/problem_dir/prompt_path are unused) —
    # route it before the prompt-path guard, like dedup/cleanup, so the orphan
    # `bridge.md` can be deleted without tripping `librarian_missing_prompt`.
    if work_kind == "bridge":
        return bridge._run_bridge(conn, problem=problem, workspace=workspace,
                           pipeline_id=pipeline_id, whitelist=whitelist)

    if work_kind not in WORK_KINDS:
        return PipelineResult(
            outcome="failed", failure_reason="librarian_bad_work_kind",
            failure_detail=f"unknown work_kind={work_kind!r}")

    prompt_path = PROMPT_DIR / "librarian" / f"{work_kind}.md"
    if not prompt_path.exists():
        return PipelineResult(
            outcome="failed", failure_reason="librarian_missing_prompt",
            failure_detail=str(prompt_path))

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
    problem_dir = db.problem_dir(workspace, problem)

    if work_kind == "migrate":
        return _run_migrate(
            conn, problem=problem, workspace=workspace,
            pipeline_id=pipeline_id, target_file=target,
            attempts_dir=attempts_dir, problem_dir=problem_dir,
            prompt_path=prompt_path, whitelist=whitelist)
    return _run_structured(
        conn, problem=problem, work_kind=work_kind, workspace=workspace,
        attempts_dir=attempts_dir, problem_dir=problem_dir,
        prompt_path=prompt_path)


def _reachable_from_root(conn, problem, workspace, slugs) -> "set[str]":
    """The slugs to KEEP for harvest: the transitive proof-usage closure of the
    harvest targets (via `inventory.usage_graph`).

    Legacy flow — the target is the proved root (`main`): keep its LIVE
    dependency closure; a proved goal NOT reachable from `main` is proving
    DEBRIS (an abandoned re-derivation / duplicate the final proof doesn't use;
    Jordan: 54/143) and is dropped.

    anchor+claim flow — when the Strategist has marked DELIVERABLES, THEY (and
    their closures) are the intended harvest targets, not the root. The root is
    never itself a deliverable (`origin='root'` can't be `MarkDeliverable`d) and
    may be vestigial scaffolding (`main : True`), so seeding from it would drop
    the real deliverables as false debris (cube_e2e 2026-07-02). Seed from the
    deliverable slugs instead."""
    from ...quality.librarian import inventory as _inv
    rs = _root_source(conn, problem, workspace)
    root_slug = rs[0] if rs else "main"
    usage = _inv.usage_graph(workspace, problem, set(slugs), root_source=rs)
    dels = db.deliverables(conn, problem=problem)
    seeds = [str(d["slug"]) for d in dels] if dels else [root_slug]
    reachable: set[str] = set()
    stack = list(seeds)
    while stack:
        s = stack.pop()
        if s in reachable:
            continue
        reachable.add(s)
        for dep in usage.get(s, set()):
            if dep not in reachable:
                stack.append(dep)
    return reachable


def _run_keepall(conn, *, problem, workspace):
    """v0.3 mechanical replacement for the agentic `dedup` step (plan §0/§3).

    Inventory the proved-goal decls, restrict to the proved root's LIVE
    dependency closure (`_reachable_from_root`), and mark every survivor `keep`
    — no keep/drop/cite/merge judgment, no spawn.

    Two reasons for the reachability filter (vs naive keep-ALL):
      1. North-star (plan §1): the Library should be exactly what `main` needs.
         Proving leaves ORPHAN DEBRIS — abandoned re-derivations / duplicate
         lemmas marked `proved` but unreachable from `main` (Jordan: 54/143).
         Library-izing them pollutes the Library with proof-thrash.
      2. Debris is often un-migratable anyway: an orphan decl can cite a DEAD
         sibling (e.g. `gaps_from_boundaries_2` → dead `gap_terms_sum`), which
         no mechanical relabel can resolve — it would hard-fail the file and
         block the chain. Filtering removes the junk before it can.

    Keeping everything in the LIVE closure is what makes migrate mechanical
    (every reference resolves to a kept sibling → no holes → no LLM) and
    deterministic (the high-variance agentic dedup — Jordan 81↔22 — is gone).
    Gate B (bridge) is the safety net if the filter ever drops a needed decl:
    `main` would fail to re-derive, loudly. Advances survivors to `deduped` so
    the existing classify step ingests them.

    Trade-off (accepted, plan §0): the kept closure still has reconstructed
    mathlib wrappers + scaffolding — verbose but self-contained; mathlib-PR
    curation (goal #2) is a future opt-in pass, not the main chain."""
    from .. import PipelineResult
    from ...quality.librarian import inventory as _inv

    # Fresh chain: drop any stale classify feedback + prior-plan scratch from a
    # prior ingestion (a reset + re-run), so the new classify starts clean.
    try:
        _pd = db.problem_dir(workspace, problem)
        _classify_feedback_path(_pd).unlink(missing_ok=True)
        _classify_prior_plan_path(_pd).unlink(missing_ok=True)
    except OSError:
        pass

    inv = _inv.build_inventory(conn, workspace, problem)
    proved_slugs = {d.slug for d in inv.decls}
    reachable = _reachable_from_root(conn, problem, workspace, proved_slugs)
    kept = [d for d in inv.decls if d.slug in reachable]
    n_orphan = len(inv.decls) - len(kept)
    if n_orphan:
        print(f"[librarian] {problem}: keep over root's live closure — "
              f"{len(kept)} reachable kept, {n_orphan} orphan proved decl(s) "
              f"skipped (debris)", flush=True)
    for d in kept:
        db.upsert_library_decl(conn, problem=problem, slug=d.slug,
                               source_goal_id=d.goal_id)
    for name in inv.defs_decls:
        # Defs decls have no proof goal — source_goal_id is None. Kept whole
        # (foundational + few); the statement / closure references them.
        db.upsert_library_decl(conn, problem=problem, slug=name,
                               source_goal_id=None)
    for r in db.library_decls_for(conn, problem):
        if r["lifecycle"] == "candidate":
            db.set_library_verdict(conn, problem=problem, slug=r["slug"],
                                   verdict="keep")
    return PipelineResult(outcome="success")


def _cleanup_scope_index(conn, problem) -> "list[tuple[str, str]]":
    """The dedup engine's scope = this problem's decls still LIVE in the
    staging Library (migrated, not-yet-cleaned + already-cleaned survivors;
    dropped ones are gone). INDEX isn't written until bridge, so the engine
    reads the problem's own decls from here instead; the pool still comes from
    INDEX (= other, already-promoted problems)."""
    return [(r["target_name"], r["target_file"])
            for r in db.library_decls_for(conn, problem)
            if r["lifecycle"] in ("migrated", "cleaned")
            and r["target_name"] and r["target_file"]]


def _advance_cleanup_decls(conn, problem, rows, dropped) -> int:
    """Advance a set of `migrated` rows past cleanup: engine-dropped (incl
    wrapper-merges) → terminal `dropped` (verdict drop + survivor citation),
    every survivor → `cleaned`. ALL must advance, else the chain re-routes to
    cleanup forever. Returns the drop count. `dropped` = {dropped_fqn:
    survivor_fqn} from the engine."""
    dropped_leaves = {f.rsplit(".", 1)[-1] for f in dropped}
    n_drop = 0
    for r in rows:
        tn = r["target_name"] or ""
        leaf = tn.rsplit(".", 1)[-1] if tn else str(r["slug"])
        if tn in dropped or leaf in dropped_leaves:
            db.set_library_verdict(conn, problem=problem, slug=r["slug"],
                                   verdict="drop", citation=dropped.get(tn))
            n_drop += 1
        else:
            db.mark_library_cleaned(conn, problem=problem, slug=r["slug"])
    return n_drop


def _run_cleanup(conn, *, problem, workspace, target_file=None, pipeline_id=None,
                 whitelist=None):
    """v0.4 cleanup stage (plan §10/§11, §13): run the dedup-audit engine on the
    migrated (staging) Library, then advance lifecycle so the chain proceeds to
    bridge. The engine owns its agent spawns + the per-decl isolate-then-splice
    gate; bridge's Gate B is the integration backstop.

    Two modes:
      - `target_file` given (§13 3c-2, the dispatcher's per-file unit): clean
        ONLY this file via `run_staged_cleanup_file`. Earlier (dependency) files'
        drops are read from the DB as `prior_renames` and applied to this file
        first (deferred-rewire — each file is written exactly once by its own
        worker, lock-free); this file's own drops are then recorded so its
        consumers self-apply them when their turn comes.
      - `target_file` None (whole-problem serial path / CLI / tests): clean every
        file in one topological pass via `run_staged_cleanup`.

    Lifecycle: dropped decls (incl wrapper-merges) → `dropped`; every surviving
    `migrated` decl → `cleaned`."""
    from .. import PipelineResult
    from ...quality.librarian import dedup as _dedup

    scope_index = _cleanup_scope_index(conn, problem)
    if target_file is not None:
        # prior_renames: incoming renames this consumer file must self-apply
        # before cleaning itself (§13 deferred-rewire), from EARLIER (dependency)
        # files — both {dropped_fqn → survivor_fqn} (drops) and
        # {old_fqn → new_fqn} (P4 renames of kept survivors). Same mechanical
        # token rewrite for both.
        all_rows = db.library_decls_for(conn, problem)
        prior_renames = {
            r["target_name"]: r["citation"]
            for r in all_rows
            if r["lifecycle"] == "dropped" and r["verdict"] == "drop"
            and r["target_name"] and r["citation"]}
        prior_renames.update({
            r["renamed_from"]: r["target_name"]
            for r in all_rows if r["renamed_from"] and r["target_name"]})
        # The whole-file mathlib-ize is ONE pass (audit): on the P13 run a
        # separate polish stage re-changed only ~7.6% of lines on top of what
        # audit already does (≈0% on the big files), so polish was folded into
        # audit (its prompt + zero-warning gate cover polish's scope) and the
        # dead polish stage has since been removed.
        res = _dedup.run_staged_cleanup_file(
            workspace, problem, target_file, scope_index=scope_index,
            prior_renames=prior_renames, apply=True,
            simplify=True, unused_args=True,
            strip_comments=True, decide=True, audit=True,
            conn=conn, pipeline_id=pipeline_id)
        # Mathlib-PR tidy: collapse redundant duplicate `variable` blocks the
        # per-decl migrate assembly replays (build-harmless, scope-safe; the
        # mechanical-path dedup missed files assembled via the LLM/Defs path —
        # StokesIntegralDefs:24/29). Source-only (variables aren't exported →
        # olean unchanged), so no rebuild needed.
        from ...quality.librarian.cleanup import _common as _C
        _fp = workspace / target_file
        try:
            _orig = _fp.read_text(encoding="utf-8")
            _coll = _C._collapse_redundant_variable_blocks(_orig)
            # Re-derive intra-file decl order from the FINAL file's references:
            # cleanup (dedup/simplify) may have rewired a proof to cite a
            # sibling, introducing a dependency `file_order` (frozen at classify)
            # doesn't reflect → a forward reference that fails the build. The
            # zero-warning gate below is the backstop if a reorder mis-parses.
            _reord = _reorder_decls_by_intrafile_refs(_coll)
            if _reord != _orig:
                _fp.write_text(_reord, encoding="utf-8")
        except OSError:
            pass
        rows = [r for r in db.library_decls_for(conn, problem, lifecycle="migrated")
                if r["target_file"] == target_file]
        # P4 decide: record {old_fqn → new_fqn} so consumer files self-apply it,
        # and refresh THIS file's olean whenever decide changed the file (decide
        # is the only stage that changes exported names OR imports — consumers
        # cleaned later typecheck against the new shape, not the stale
        # migrate-time olean). Record before advancing lifecycle
        # (set_library_renamed only updates target_name/renamed_from).
        renamed = res.get("renamed", {})
        imports_min = bool(res.get("imports_min"))
        audited = bool(res.get("audited"))
        if renamed:
            slug_by_fqn = {r["target_name"]: r["slug"] for r in rows}
            for old_fqn, new_fqn in renamed.items():
                slug = slug_by_fqn.get(old_fqn)
                if slug:
                    db.set_library_renamed(conn, problem=problem, slug=slug,
                                           old_fqn=old_fqn, new_fqn=new_fqn)
        if renamed or imports_min or audited:
            from .._lake import lake_build_modules
            # NOT best-effort: this rebuild is load-bearing. `lake_build_modules`
            # returns (ok, out) and does NOT raise on a build failure (only an
            # internal TimeoutExpired is caught) — so the old `try/except: pass`
            # silently dropped failures, leaving a stale (old-name) olean that
            # makes every consumer's per-file gate fail with confusing errors and
            # the chain silent-stall. Surface it loudly instead.
            ok, out = lake_build_modules(
                workspace, [_dedup._mod_of_rel(target_file)])
            if not ok:
                return PipelineResult(
                    outcome="failed",
                    failure_reason="librarian_cleaned_build_failed",
                    failure_detail=(f"decide olean refresh failed for "
                                    f"{target_file}: {out[-400:]}"))
        # Hard Mathlib-PR gate: the finalized file must build WARNING-FREE.
        # Deprecated lemmas, unused variables, style lints etc. are the
        # "auto-generated" tells that would block a real mathlib PR. On a build
        # error or any residual warning, FAIL the unit — the chain retries
        # cleanup (re-spawning audit/polish to clear them); if it cannot, the
        # STALL line surfaces the blocker (df77f05). audit may justify-suppress a
        # genuinely unavoidable lint with `set_option … false in`.
        try:
            _final = (workspace / target_file).read_text(encoding="utf-8")
        except OSError:
            _final = None                            # absent (e.g. unit tests) → skip
        if _final is not None:
            _wok, _wout = _C._build_for_warnings(
                workspace, _final, prefix="_cleanup_warngate")
            _warns = _C._all_warnings(_wout)
            if not _wok or _warns:
                return PipelineResult(
                    outcome="failed",
                    failure_reason=("librarian_cleaned_build_failed" if not _wok
                                    else "librarian_warnings_remain"),
                    failure_detail=(
                        f"{target_file}: "
                        + (f"build failed:\n{_wout[-400:]}" if not _wok else
                           f"{len(_warns)} residual warning(s) — Mathlib PR bar "
                           "is zero:\n" + "\n".join(_warns[:10]))))
        # Post-rewrite axiom gate (principle: every high-risk rewrite must
        # re-pass the axiom gate). cleanup's LLM stages — simplify, near-dup
        # bridge one-liners, audit's whole-file rewrite — run AFTER migrate's
        # per-decl axiom check and are the only post-migrate stages that can
        # change a decl's transitive axiom set (`by native_decide` builds
        # green and warning-free but pulls in `Lean.ofReduceBool`). Re-run the
        # SAME per-decl `#print axioms ⊆ whitelist` probe on the FINAL text:
        # decl names are extracted from it post-rename, so decide/audit
        # renames and any audit-ADDED declaration are covered. One extra warm
        # elaboration per file. `whitelist=None` (unit tests / legacy callers)
        # skips, matching the migrate gate's contract; the dispatcher always
        # passes the Manifest whitelist (or the framework default).
        if _final is not None and whitelist is not None:
            from . import gate as _gate
            gres = _gate.migrate_commit_gate(
                _final, workspace / target_file,
                whitelist=whitelist, workspace=workspace)
            if not gres.ok:
                return PipelineResult(
                    outcome="failed",
                    failure_reason="librarian_axiom_violation",
                    failure_detail=(f"post-cleanup axiom gate: {target_file}: "
                                    f"{gres.detail}"))
        n_drop = _advance_cleanup_decls(conn, problem, rows, res.get("dropped", {}))
        print(f"[librarian] {problem}: cleanup `{target_file}` — {n_drop} "
              f"dropped, {len(res.get('bridged', {}))} bridged, "
              f"{len(renamed)} renamed, imports_min={imports_min}, "
              f"audited={audited}; survivors → cleaned", flush=True)
        return PipelineResult(outcome="success")

    migrated = list(db.library_decls_for(conn, problem, lifecycle="migrated"))
    res = _dedup.run_staged_cleanup(
        workspace, problem, apply=True, scope_index=scope_index, conn=conn)
    # Same post-rewrite axiom gate as the per-file path above, applied to every
    # file this serial pass touched (CLI / whole-problem mode). A file the
    # engine dropped entirely no longer exists → skip it.
    if whitelist is not None:
        from . import gate as _gate
        for _tf in sorted({r["target_file"] for r in migrated
                           if r["target_file"]}):
            try:
                _txt = (workspace / _tf).read_text(encoding="utf-8")
            except OSError:
                continue
            gres = _gate.migrate_commit_gate(
                _txt, workspace / _tf, whitelist=whitelist,
                workspace=workspace)
            if not gres.ok:
                return PipelineResult(
                    outcome="failed",
                    failure_reason="librarian_axiom_violation",
                    failure_detail=(f"post-cleanup axiom gate: {_tf}: "
                                    f"{gres.detail}"))
    n_drop = _advance_cleanup_decls(conn, problem, migrated, res.get("dropped", {}))
    print(f"[librarian] {problem}: cleanup — {n_drop} dropped, "
          f"{len(res.get('bridged', {}))} bridged; survivors → cleaned",
          flush=True)
    return PipelineResult(outcome="success")


def _classify_feedback_path(problem_dir) -> "_Path":
    """Cross-dispatch scratch carrying the prior classify rejection. classify is
    a one-shot spawn per dispatch and the chain re-dispatches fresh on failure,
    so this `.drafts/` file (persists across dispatches, unlike `.attempts/`) is
    how attempt N+1's Context.md learns what attempt N got wrong."""
    return problem_dir / ".drafts" / "classify_feedback.txt"


def _classify_prior_plan_path(problem_dir) -> "_Path":
    """Cross-dispatch scratch holding the prior attempt's (parsed) plan.json, so
    a retry EDITS it incrementally rather than re-deriving the whole layout —
    which re-drops declarations (whack-a-mole). Saved only when the prior plan
    parsed (a verify-stage rejection); cleared on a schema-invalid attempt
    (nothing valid to edit) and on success."""
    return problem_dir / ".drafts" / "classify_prior_plan.json"


def _classify_trap_budget(n_decls: int) -> int:
    """Watchdog `trap_check_sec` for a classify spawn — it scales with N, the
    number of decls the agent lays out in ONE thinking block. The global 660s
    is calibrated for BOUNDED spawns (builder/backward/migrate each work one
    goal/patch/file); classify's input is unbounded and its think time grows
    with N (residue 271 decls → ~650s, killed before it emitted the plan), so a
    cap-bounded `base + per_decl·N` gives a large layout room without a magic
    flat constant. Other kinds keep the global value (override left None)."""
    from ...core import config as _cfg
    base = _cfg.get("dispatch.trap_check_sec", default=660,
                    env_var="ASTERISM_TRAP_CHECK_SEC", cast=int)
    per_decl = _cfg.get("dispatch.classify_trap_per_decl_sec",
                        default=4, cast=int)
    cap = _cfg.get("dispatch.classify_trap_cap_sec", default=2400, cast=int)
    return min(cap, base + per_decl * max(0, n_decls))


def _run_structured(conn, *, problem, work_kind, workspace,
                    attempts_dir, problem_dir, prompt_path):
    """classify: one-shot spawn emitting plan.json, then parse + verify +
    commit (all-or-nothing). Mirrors run_strategist. (v0.3: `dedup` no longer
    routes here — it is the mechanical `_run_keepall`.)"""
    import uuid
    from .. import PipelineResult, _feedback
    from ... import agent

    fb_path = _classify_feedback_path(problem_dir)
    plan_path = _classify_prior_plan_path(problem_dir)
    is_classify = work_kind == "classify"
    prev_error = (fb_path.read_text(encoding="utf-8")
                  if is_classify and fb_path.exists() else None)
    prior_plan = (plan_path.read_text(encoding="utf-8")
                  if is_classify and prev_error and plan_path.exists() else None)

    def _reject(reason: str, detail: str,
                prior: "str | None" = None) -> "PipelineResult":
        # Persist the rejection + (when the plan parsed) the prior plan, so the
        # next (fresh) classify dispatch EDITS it incrementally instead of
        # re-deriving the whole layout. classify-only cross-attempt feedback.
        if is_classify:
            try:
                fb_path.parent.mkdir(parents=True, exist_ok=True)
                fb_path.write_text(detail, encoding="utf-8")
                if prior is not None:
                    plan_path.write_text(prior, encoding="utf-8")
                else:                                  # nothing valid to edit
                    plan_path.unlink(missing_ok=True)
            except OSError:
                pass
        return PipelineResult(outcome="failed", failure_reason=reason,
                              failure_detail=detail)

    compile_librarian_context(
        conn, problem=problem, work_kind=work_kind,
        attempts_dir=attempts_dir, workspace=workspace,
        prev_error=prev_error, prior_plan=prior_plan)

    sid = str(uuid.uuid4())
    # classify reasons over the whole kept-decl set in one thinking block, so
    # give the watchdog a size-scaled trap_check (and a matching overall
    # timeout that keeps the same post-trap window the default config has).
    trap_override = None
    timeout_override = None
    if is_classify:
        from ...core import config as _cfg
        n_kept = len(db.library_decls_for(conn, problem, lifecycle="deduped"))
        trap_override = _classify_trap_budget(n_kept)
        base = _cfg.get("dispatch.trap_check_sec", default=660,
                        env_var="ASTERISM_TRAP_CHECK_SEC", cast=int)
        spawn_to = _cfg.get("dispatch.spawn_timeout_sec", default=960,
                            env_var="ASTERISM_SPAWN_TIMEOUT_SEC", cast=int)
        timeout_override = trap_override + max(0, spawn_to - base)
    from .. import write_tools_mcp_config as _write_tools_cfg
    rc = agent.spawn_llm(
        kind="librarian", prompt_path=prompt_path,
        problem_dir=problem_dir, attempts_dir=attempts_dir,
        session_id=sid,
        trap_check_sec_override=trap_override,
        timeout_sec_override=timeout_override,
        # dedup_audit and migrate both search Mathlib for a twin; loogle
        # is an MCP tool now, so without this the prompt names a tool the
        # agent cannot call.
        mcp_config_path=_write_tools_cfg(attempts_dir, workspace))
    if rc != 0:
        return PipelineResult(
            outcome="failed", failure_reason="agent_error",
            failure_detail=f"agent rc={rc}")

    out_path = attempts_dir / "plan.json"
    if not out_path.exists():
        return PipelineResult(
            outcome="failed", failure_reason="agent_no_output",
            failure_detail="no plan.json")
    text = out_path.read_text(encoding="utf-8")

    plan, err = parse_classify(text)
    if err:
        return _reject("librarian_schema_invalid", err)
    kept = {r["slug"] for r in db.library_decls_for(conn, problem,
                                                    lifecycle="deduped")}
    owned = {r["target_file"].replace("\\", "/") for r in conn.execute(
        "SELECT DISTINCT target_file FROM library_decls WHERE problem != ? "
        "AND lifecycle IN ('classified', 'migrated', 'cleaned') "
        "AND target_file IS NOT NULL", (problem,))}
    decl_lines = _decl_line_counts(workspace, problem, kept)
    verr = verify_classify(plan, kept, decl_lines=decl_lines, owned_files=owned)
    if verr:
        return _reject("librarian_verify_failed", verr, prior=text)
    # Post-merge size gate: the per-planned-file check above misses an
    # un-splittable usage SCC (cyclic file group) that merges several files into
    # one over-budget Lean module — which would later STALL forever at the audit
    # zero-warning gate on `longFile`. Compute the merge NOW and reject so the
    # agent re-partitions (the decl usage graph is a DAG; the file cycle is its
    # grouping artifact). Reuse the (usage, canon) for commit so usage_graph
    # runs once.
    usage_canon = _plan_usage_and_canon(conn, problem, plan, workspace)
    merr = verify_merged_file_sizes(plan, usage_canon[1], decl_lines,
                                    usage=usage_canon[0])
    if merr:
        return _reject("librarian_verify_failed", merr, prior=text)
    commit_classify(conn, problem, plan, workspace, precomputed=usage_canon)
    # Plan accepted — drop the cross-attempt feedback + prior-plan scratch so a
    # future re-classify of this problem starts clean.
    try:
        fb_path.unlink(missing_ok=True)
        plan_path.unlink(missing_ok=True)
    except OSError:
        pass
    # Framework-feedback (`agent_feedback.md`, NOT the cross-attempt fb_path
    # above): classify lays out the whole kept-decl set in one heavy spawn and
    # had the widest inside view of the layout task, yet — unlike builder /
    # backward — never recorded a single pain-point because this bespoke spawn
    # path skipped attempt_feedback entirely. Ask once on a committed plan
    # (the sid is still resumable here); reject paths already feed prev_error.
    if is_classify:
        _feedback.attempt_feedback(
            kind="classify", sid=sid, slug="layout",
            outcome="success", problem_dir=problem_dir,
            attempts_dir=attempts_dir, workspace=workspace)
    return PipelineResult(outcome="success")
