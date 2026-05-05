"""Backward pipeline. OR-parallel-safe decomposition: reserves a fresh
strategy id, writes scratch + namespaced sub-goal files at strategy-
isolated paths, runs Lean kernel isDefEq dedupe to collapse equivalent
sub-goals to alias bodies, places everything atomically.

Public entry point: `run_backward`. Backward-specific helpers
(`_ensure_imports_subgoal`, `_try_promote_sorry_free`,
`_parse_entry_kind`) live here. Shared helpers (`_grep_forbidden`,
`_attempt_postmortem`, `_spawn_failure`, `_safe_glob`,
`_signature_prefix`, `_normalize_signature`, `_build_strategy_skeleton`,
`_inject_imports_for_subs`, `_lean_path_to_module`, `_lake_build_batch`,
`PipelineResult`, `PROMPT_DIR`, `DECLINE_*`, `_parse_decline_reason`,
`_drafts`, `_extract_statement_from_lean`, `_slug_from_filename`) are
imported from the package root.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path

from .. import agent, db, dedupe, diagnostics, manifest
from ..llm.base import SpawnRC


# ---------------------------------------------------------------------
# Backward-specific helpers (no shared callers as of writing)
# ---------------------------------------------------------------------

def _ensure_imports_subgoal(
    content: str, *, problem: str, workspace: Path,
) -> str:
    """Prepend `import Mathlib` and `import Problems.<problem>.Defs`
    (when the problem ships a `Defs.lean`) if missing. Idempotent —
    skips any line already present.

    Without `Defs`, problem-level custom symbols (e.g. SG's `Collinear`)
    are unresolved; a strict agent following the prompt's "framework
    auto-injects imports" instruction writes none, and Lean falls back
    to whatever `import Mathlib` exposes (e.g. Mathlib's universe-poly
    `Collinear (k : Type*) ...`), breaking elaboration.
    """
    needed: list[str] = []
    if not re.search(r"(?m)^import\s+Mathlib\b", content):
        needed.append("import Mathlib")
    defs_path = workspace / "Problems" / problem / "Defs.lean"
    if defs_path.exists():
        defs_module = f"Problems.{problem}.Defs"
        if not re.search(rf"(?m)^import\s+{re.escape(defs_module)}\b",
                         content):
            needed.append(f"import {defs_module}")
    if not needed:
        return content
    return "\n".join(needed) + "\n\n" + content


# Backward-placement convention: each `new_<sub_slug>.lean` should land
# with body `:= by sorry`. Agents occasionally inline a full proof
# instead (observed on SG s75_sub_4 — agent collapsed the sub-goal with
# `by_contra + ring + nlinarith`). When that happens AND axioms are in
# whitelist, we skip the now-redundant Backward dispatch and mark the
# sub-goal proved upfront. The check is fast: `\bsorry\b` substring
# match first (microseconds; 99% of placements have sorry); only the
# rare sorry-free case pays the axiom-probe cost.
_SORRY_RE = re.compile(r"\b(?:sorry|sorryAx)\b")


def _try_promote_sorry_free(
    *, dest: Path, problem: str, slug: str, workspace: Path,
    axioms_whitelist: list[str],
) -> tuple[bool, str]:
    """If `dest` is sorry-free AND its `#print axioms` set is a subset
    of `axioms_whitelist`, return (True, msg). Otherwise (False, reason).

    The strategy's batch lake build at the caller's site already
    confirmed the file compiles, so we skip a redundant compile here
    and only run `#print axioms` on the candidate identifier.

    Empty whitelist → reject (the project clearly didn't authorize
    bypassing the axiom gate; conservative path is to dispatch).
    """
    from . import _lean_path_to_module  # late-import via package root
    try:
        content = dest.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"read failed: {exc}"
    if _SORRY_RE.search(content):
        return False, "body contains sorry"
    if not axioms_whitelist:
        return False, "no axioms_whitelist"
    fq_name = f"Problems.{problem}.{slug}"
    module = _lean_path_to_module(workspace, dest)
    probe = workspace / f"_axiom_probe_{slug}.lean"
    probe.write_text(
        f"import {module}\n#print axioms {fq_name}\n",
        encoding="utf-8",
    )
    try:
        r = subprocess.run(
            ["lake", "env", "lean", str(probe)],
            cwd=str(workspace), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return False, f"axiom probe failed: {exc}"
    finally:
        probe.unlink(missing_ok=True)
    if r.returncode != 0:
        return False, f"axiom probe rc={r.returncode}"
    used: set[str] = set()
    m = re.search(r"depends on axioms?\s*:\s*\[(.*?)\]",
                  r.stdout, re.DOTALL)
    if m:
        for a in m.group(1).split(","):
            a = a.strip()
            if a:
                used.add(a)
    rogue = used - set(axioms_whitelist)
    if rogue:
        return False, f"rogue axioms: {sorted(rogue)}"
    return True, f"axioms ok: {sorted(used) or '[]'}"


# `entry_kind: Builder` or `entry_kind: Backward` directive — the
# Backward agent annotates each `new_<slug>.lean` with this comment so
# the framework knows whether to dispatch this sub-goal to Builder
# (one-shot tactic + LLM patch) or skip straight to Backward
# decomposition. Comment-form (not YAML frontmatter) so it sits next to
# the theorem definition the agent is reasoning about.
_ENTRY_KIND_RE = re.compile(
    r"(?m)^\s*--\s*entry_kind\s*:\s*(Builder|Backward)\b"
)


def _parse_entry_kind(lean_text: str) -> str:
    """Extract the `-- entry_kind: ...` directive from a sub-goal lean
    file. Returns 'Builder' or 'Backward' (capitalized as in the DB
    enum); defaults to 'Builder' if the directive is absent or
    unrecognized. The default mirrors the legacy attempts-only routing
    so a missing directive doesn't change behavior."""
    m = _ENTRY_KIND_RE.search(lean_text)
    return m.group(1) if m else "Builder"


def _fetch_last_backward_error(conn: sqlite3.Connection,
                               goal_id: int) -> str:
    """F53 — most recent Backward lake error on this goal. Inlined as
    retry_context so the same-session resume agent sees what its prior
    turn produced + how lake rejected it, without re-reading any
    companion file."""
    row = conn.execute(
        "SELECT da.failure_detail FROM dead_attempts da"
        " JOIN pipelines p ON p.id = da.pipeline_id"
        " WHERE da.target_id = ? AND da.target_kind = 'Goal'"
        "   AND p.kind = 'Backward'"
        " ORDER BY da.id DESC LIMIT 1",
        (goal_id,),
    ).fetchone()
    if row is None or not row["failure_detail"]:
        return ""
    return diagnostics.strip_lake_noise(row["failure_detail"])


# ---------------------------------------------------------------------
# Pipeline entry
# ---------------------------------------------------------------------

def run_backward(conn: sqlite3.Connection, *, goal_id: int,
                 workspace: Path, mfst: manifest.Manifest,
                 pipeline_id: str) -> "PipelineResult":  # noqa: F821
    """Outer dispatch — runs the inner Backward then persists or clears
    the partial-output draft (F55) so a future spawn on this same goal
    sees the in-flight PROPOSAL.md from the prior failed/timed-out
    attempt instead of starting from scratch.

    Outcomes:
      - `success`: strategy committed → clear any prior draft.
      - `failed` with `failure_reason == "goal_no_longer_open"`: the
        race-guard fired because a sibling (re)decomposed or shelved
        this goal mid-spawn. The persisted PROPOSAL.md is moot for any
        future Backward — clear instead of persisting a stale draft
        that would mislead a re-decomposition if the goal later reopens.
      - anything else (rc!=0, parse_proposal_fail, signature mismatch,
        ...): persist what the spawn wrote.
    """
    from . import PipelineResult, _drafts
    goal_row = db.get_goal(conn, goal_id)
    if goal_row is None:
        return PipelineResult(outcome="failed", failure_reason="goal_not_found")
    problem_dir = workspace / "Problems" / goal_row["problem"]
    result = _run_backward_inner(conn, goal_id=goal_id, workspace=workspace,
                                 mfst=mfst, pipeline_id=pipeline_id)
    if (result.outcome == "success"
            or result.failure_reason == "goal_no_longer_open"):
        _drafts.clear_partial(problem_dir=problem_dir, kind="backward",
                              goal_id=goal_id)
    else:
        attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)
        _drafts.persist_partials(attempts_dir=attempts_dir,
                                 problem_dir=problem_dir,
                                 kind="backward", goal_id=goal_id)
    return result


def _run_backward_inner(conn: sqlite3.Connection, *, goal_id: int,
                        workspace: Path, mfst: manifest.Manifest,
                        pipeline_id: str) -> "PipelineResult":  # noqa: F821
    """OR-parallel-safe Backward.

    Each invocation reserves a fresh strategy id and writes its scratch +
    namespaced sub-goal files at strategy-isolated paths. Multiple
    concurrent Backwards on the same parent therefore never collide on
    the filesystem, the goals table (slug uniqueness), or the parent's
    own lean_path (which is left untouched until Verify wins).
    """
    from . import (
        PipelineResult, PROMPT_DIR,
        _attempt_postmortem, _build_strategy_skeleton,
        _extract_statement_from_lean, _grep_forbidden,
        _inject_imports_for_subs, _lake_build_batch,
        _lean_path_to_module, _normalize_signature,
        _parse_decline_reason, _safe_glob,
        _signature_prefix, _slug_from_filename, _spawn_failure,
        DECLINE_PARENT_TYPE_INFEASIBLE,
    )

    goal = db.get_goal(conn, goal_id)
    if goal is None:
        return PipelineResult(outcome="failed", failure_reason="goal_not_found")

    attempts_dir = agent.attempts_dir_for(workspace, pipeline_id)

    # F53 — same-session Backward retry (mirror of F33 for Builder).
    # First dispatch on a goal mints a session UUID and pins it via
    # --session-id; subsequent dispatches `claude --resume` so the
    # agent's prior thinking + tool reads + lake-error perception
    # carry over. retry_context inlines the latest lake stderr so the
    # resumed agent sees what its prior turn produced and how lake
    # rejected it.
    sid = db.get_backward_session_id(conn, goal_id)
    is_retry = sid is not None

    # F53/A — reuse the prior dead strategy's id across warm retries.
    # Agent's session memory anchors on the slug it wrote last turn
    # (`L_s152_sub_*`). If this dispatch mints a fresh strategy_id
    # (s153, s154, ...), the resumed agent keeps writing the stale
    # `s152_sub_*` slugs and trips `naming_violation` every time.
    # Pinning sid_token to the prior strategy keeps Context.md, the
    # F52 skeleton, and the agent's session-memory all using the
    # same slug.
    strategy_id: int | None = None
    if is_retry:
        row = conn.execute(
            "SELECT id FROM strategies "
            "WHERE goal_id = ? AND status = 'dead' "
            "ORDER BY id DESC LIMIT 1",
            (goal_id,),
        ).fetchone()
        if row is not None:
            strategy_id = int(row["id"])
            # P0-#3: clear any stale `strategy_subgoals` links from
            # the prior dead cycle. If the previous Backward had
            # committed sub-goals (currently only reachable on full
            # success, which clears session_id and prevents this
            # branch — but defensive against future code paths), the
            # resurrected strategy would otherwise carry ghost links
            # whose subgoal goal-rows are stale. Concretely
            # `strategies_ready_for_verify` checks every linked sub;
            # ghost-but-proved subs would falsely mark the strategy
            # ready for Verify before this Backward had even written
            # the new ones.
            conn.execute(
                "DELETE FROM strategy_subgoals WHERE strategy_id = ?",
                (strategy_id,),
            )
            conn.execute(
                "UPDATE strategies "
                "SET status='proposed', created_by=?, scratch_path='', "
                "    proposal_md='' WHERE id=?",
                (pipeline_id, strategy_id),
            )
            conn.commit()
    if strategy_id is None:
        strategy_id = db.insert_strategy(
            conn, goal_id=goal_id, lean_path=goal["lean_path"],
            created_by=pipeline_id, proposal_md="", scratch_path="",
        )
    sid_token = f"s{strategy_id}"

    def _abort(reason: str, detail: str = "",
               proposal_md: str = "") -> "PipelineResult":
        db.update_strategy_status(conn, strategy_id, "dead")
        return PipelineResult(
            outcome="failed", failure_reason=reason,
            failure_detail=detail, proposal_md=proposal_md,
        )

    retry_context: str | None = None
    if not is_retry:
        # P1-#7: mint UUID locally; persist AFTER spawn (mirror
        # builder block above).
        sid = str(uuid.uuid4())
        agent.compile_context(conn, goal=goal, mfst=mfst,
                              attempts_dir=attempts_dir,
                              strategy_id=strategy_id, kind="backward")
    else:
        retry_context = _fetch_last_backward_error(conn, goal_id)

    # F52 — pre-write strategy patch skeleton: copy parent stub's
    # `theorem <slug> <binders> : <type>` declaration verbatim, rename
    # to `theorem sX`, body = `by sorry`. Agent edits ONLY the body;
    # framework rejects any signature edit via `_signature_prefix` diff.
    # Under F53/A the strategy_id is stable across warm retries, so
    # the skeleton's `theorem sX` head matches both the prior turn's
    # session memory and the current Context.md naming convention.
    parent_abs_for_skeleton = workspace / goal["lean_path"]
    try:
        parent_text = parent_abs_for_skeleton.read_text(encoding="utf-8")
    except OSError as exc:
        return _abort("missing_parent_stub", str(exc))
    namespace = f"Problems.{goal['problem']}"
    skeleton = _build_strategy_skeleton(
        parent_text,
        parent_slug=goal["slug"],
        sid_token=sid_token,
        namespace=namespace,
    )
    if skeleton is None:
        return _abort(
            "parent_stub_not_decomposable",
            f"theorem {goal['slug']} not found in {goal['lean_path']} "
            f"(may have been promoted by a sibling already)",
        )
    skeleton_path = attempts_dir / "patch.lean"
    skeleton_path.write_text(skeleton, encoding="utf-8")
    skeleton_signature = _normalize_signature(
        _signature_prefix(skeleton, sid_token))

    spawn_t0 = time.monotonic()
    rc = agent.spawn_llm(
        kind="backward",
        prompt_path=PROMPT_DIR / "backward.md",
        problem_dir=workspace / "Problems" / goal["problem"],
        attempts_dir=attempts_dir,
        session_id=sid,
        is_retry=is_retry,
        retry_context=retry_context,
    )
    spawn_dur = time.monotonic() - spawn_t0

    # P1-#7: persist after spawn proves session exists.
    if not is_retry and rc not in (SpawnRC.TIMEOUT, SpawnRC.STALE_SESSION):
        db.set_backward_session_id(conn, goal_id, sid)

    # F53 — claude session may have been GC'd between dispatches
    # (rc=125). Mint a fresh UUID, recompile context, cold-spawn once.
    if rc == SpawnRC.STALE_SESSION:
        db.set_backward_session_id(conn, goal_id, None)
        sid = str(uuid.uuid4())
        agent.compile_context(conn, goal=goal, mfst=mfst,
                              attempts_dir=attempts_dir,
                              strategy_id=strategy_id, kind="backward")
        spawn_t0 = time.monotonic()
        rc = agent.spawn_llm(
            kind="backward",
            prompt_path=PROMPT_DIR / "backward.md",
            problem_dir=workspace / "Problems" / goal["problem"],
            attempts_dir=attempts_dir,
            session_id=sid,
            is_retry=False,
        )
        spawn_dur = time.monotonic() - spawn_t0
        if rc not in (SpawnRC.TIMEOUT, SpawnRC.STALE_SESSION):
            db.set_backward_session_id(conn, goal_id, sid)

    if rc == SpawnRC.TIMEOUT:
        # Timeout: agent SIGKILL'd mid-write. F55 — postmortem spawn
        # resumes the killed session for a short state-dump into
        # `_progress.md` before we clear the session id (the wrapper
        # then persists _progress.md as the partial draft).
        if sid is not None:
            _attempt_postmortem(
                kind="backward",
                prompt_path=PROMPT_DIR / "backward_postmortem.md",
                problem_dir=workspace / "Problems" / goal["problem"],
                attempts_dir=attempts_dir,
                session_id=sid,
            )
        db.set_backward_session_id(conn, goal_id, None)
        reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
        return _abort(reason, detail)
    if rc != 0:
        # Ordinary failure — keep session_id so the next dispatch's
        # --resume has the prior failed-turn context to learn from.
        reason, detail = _spawn_failure(rc, attempts_dir, spawn_dur)
        return _abort(reason, detail)

    proposal = attempts_dir / "PROPOSAL.md"
    if not proposal.exists():
        return _abort("parse_proposal_fail", "no PROPOSAL.md")
    proposal_text = proposal.read_text(encoding="utf-8")

    patches = _safe_glob(attempts_dir, "patch*.lean")
    new_subs = _safe_glob(attempts_dir, "new_*.lean")
    if not patches or not new_subs:
        # Backward decline channel. Mirrors Builder's F48 hatch: an agent
        # that finds the goal infeasible (counterexample available, or
        # it sees no honest decomposition) writes only PROPOSAL.md with
        # `decline_reason: parent_type_infeasible` — framework cascades
        # up rather than charging another wasted attempt.
        reason = _parse_decline_reason(proposal_text)
        if reason == DECLINE_PARENT_TYPE_INFEASIBLE:
            return _abort(
                "agent_infeasible",
                ("backward reports parent type infeasible; "
                 "PROPOSAL.md must include counterexample"),
                proposal_text,
            )
        return _abort(
            "parse_proposal_fail",
            f"patch={len(patches)} new={len(new_subs)}",
            proposal_text,
        )

    all_text = "\n".join(p.read_text(encoding="utf-8")
                         for p in patches + new_subs)
    forbidden = _grep_forbidden(all_text, mfst.forbidden_lemmas)
    if forbidden:
        return _abort("forbidden_lemma", forbidden, proposal_text)

    # F52 — diff check: agent must preserve the framework-locked
    # signature `theorem sX <binders> : <type>`. Whitespace normalized
    # so re-indentation is OK; binder/type changes are not.
    main_patch_text = patches[0].read_text(encoding="utf-8")
    agent_signature = _normalize_signature(
        _signature_prefix(main_patch_text, sid_token))
    if agent_signature != skeleton_signature:
        return _abort(
            "patch_signature_mismatch",
            f"agent edited the locked signature\n"
            f"expected: {skeleton_signature[:300]}\n"
            f"got:      {agent_signature[:300]}",
            proposal_text,
        )

    # Validate slug naming convention: every sub-goal filename must be
    # `new_<sid_token>_sub_<N>.lean`.
    expected_prefix = f"{sid_token}_sub_"
    sub_meta: list[tuple[str, Path]] = []  # (slug, source_in_attempts)
    for ns in new_subs:
        slug = _slug_from_filename(ns.name)
        if not slug.startswith(expected_prefix):
            return _abort(
                "naming_violation",
                f"sub-goal slug {slug!r} does not start with {expected_prefix!r}",
                proposal_text,
            )
        sub_meta.append((slug, ns))

    # Dedupe scan: batch-call Lean kernel isDefEq for all candidate
    # sub-goals × eligible ancestors in one subprocess. Hits → write an
    # alias lean file that delegates to canonical via `apply <;>
    # assumption`; insert the alias goal as 'proved' (its proof IS the
    # alias body).
    candidates_for_dedupe: list[tuple[str, str]] = []
    for slug, src in sub_meta:
        try:
            candidates_for_dedupe.append(
                (slug, src.read_text(encoding="utf-8")))
        except OSError:
            candidates_for_dedupe.append((slug, ""))
    canonical_for = dedupe.find_canonicals_batch(
        conn, workspace,
        problem=goal["problem"],
        parent_goal_id=goal_id,
        candidates=candidates_for_dedupe,
    )

    # Compute permanent paths under proofs/. No collision possible
    # because every path includes sid_token.
    proofs_dir = workspace / "Problems" / goal["problem"] / "proofs"
    proofs_dir.mkdir(parents=True, exist_ok=True)
    scratch_filename = f"_strategy_{sid_token}.lean"
    scratch_dest = proofs_dir / scratch_filename
    sub_dests = [(slug, proofs_dir / f"L_{slug}.lean") for slug, _ in sub_meta]

    placed: list[Path] = []
    try:
        # Place sub-goal files: alias body for dedupe-hits, original
        # content for novel sub-goals.
        for (slug, src), (_, dest), canonical_id in zip(
            sub_meta, sub_dests, canonical_for,
        ):
            if canonical_id is not None:
                canonical = db.get_goal(conn, canonical_id)
                canonical_module = _lean_path_to_module(
                    workspace, workspace / canonical["lean_path"])
                original_content = src.read_text(encoding="utf-8")
                dest.write_text(
                    dedupe.build_alias_content(
                        original_content=original_content,
                        canonical_module=canonical_module,
                        canonical_slug=canonical["slug"],
                    ),
                    encoding="utf-8",
                )
                print(f"[dedupe] {slug} → goal {canonical_id} "
                      f"({canonical['slug']})", flush=True)
            else:
                content = _ensure_imports_subgoal(
                    src.read_text(encoding="utf-8"),
                    problem=goal["problem"], workspace=workspace,
                )
                dest.write_text(content, encoding="utf-8")
            placed.append(dest)
        shutil.copy2(patches[0], scratch_dest)
        placed.append(scratch_dest)

        # F52 — auto-inject `import` lines for sub-goal modules into
        # the strategy patch. Agents reliably forget at least one;
        # framework-managed imports avoid an entire class of
        # `unknown identifier` errors at lake build.
        sub_dest_paths = [dest for _, dest in sub_dests]
        _inject_imports_for_subs(workspace, scratch_dest, sub_dest_paths)

        # F23 — single multi-target lake invocation. Lake's internal
        # scheduler builds independent sub-goal files in parallel and
        # serializes the strategy assembly (which imports the subs)
        # after, replacing the prior serial per-file loop. On a 4-sub
        # strategy the wall-clock dropped from ~5×80s to ~max(80s)+80s.
        # Caller (annotate_failure_detail) smart-truncates stderr to
        # surface error / warning lines.
        ok, err = _lake_build_batch(workspace, placed)
        if not ok:
            raise RuntimeError(f"lake build failed: {err}")

        # F24-A — race guard: between this Backward's dispatch and now
        # (which is up to several minutes due to claude CLI + lake build),
        # an OR-parallel sibling may have shelved or proved this goal.
        # Either way our new strategy is moot. Abort cleanly so cascade
        # has nothing to mutate; clean up sub-goal files we placed.
        # cascade_one's no-op guard handles the same race on its side
        # (defense in depth) — this layer prevents the orphan strategy +
        # sub-goal rows from ever reaching the DB.
        fresh = db.get_goal(conn, goal_id)
        if fresh is None or fresh["status"] not in ("open", "attempting"):
            for p in placed:
                try:
                    if p.exists():
                        p.unlink()
                except OSError:
                    pass
            current = fresh["status"] if fresh else "missing"
            return _abort(
                "goal_no_longer_open",
                f"goal {goal_id} transitioned to {current!r} during this "
                f"Backward's run; aborting to avoid orphan strategy.",
                proposal_text,
            )

        # All passed — INSERT goals + link via strategy_subgoals.
        # Dedupe-hits are inserted as already-'proved' (alias body is
        # the proof); novel sub-goals start 'open'. Sorry-free
        # placements with whitelisted axioms also start 'proved' —
        # spares a redundant Backward/Builder spawn that would just
        # `promote_to_alias` over the same content.
        linked_ids: list[int] = []
        for (slug, dest), canonical_id in zip(sub_dests, canonical_for):
            stmt = _extract_statement_from_lean(dest)
            rel = dest.relative_to(workspace).as_posix()
            entry_kind = _parse_entry_kind(
                dest.read_text(encoding="utf-8"))
            new_gid = db.insert_goal(
                conn, problem=goal["problem"], slug=slug,
                lean_path=rel, statement=stmt, origin="backward",
                depth=goal["depth"] + 1,
                entry_kind=entry_kind,
            )
            if canonical_id is not None:
                db.update_goal_status(conn, new_gid, "proved")
                # F42 — record alias relationship so prune retains the
                # canonical (in case it's an orphan from a dead strategy)
                # for as long as this alias is alive.
                db.set_alias_target(conn, new_gid, canonical_id)
            else:
                ok, msg = _try_promote_sorry_free(
                    dest=dest, problem=goal["problem"], slug=slug,
                    workspace=workspace,
                    axioms_whitelist=mfst.axioms_whitelist,
                )
                if ok:
                    db.update_goal_status(conn, new_gid, "proved")
                    print(f"[skip-dispatch] {slug} → proved ({msg})",
                          flush=True)
            linked_ids.append(new_gid)
        for pos, gid in enumerate(linked_ids):
            db.link_subgoal(conn, strategy_id=strategy_id,
                            subgoal_id=gid, position=pos)

        scratch_rel = scratch_dest.relative_to(workspace).as_posix()
        db.update_strategy_scratch_path(conn, strategy_id, scratch_rel)
        conn.execute("UPDATE strategies SET proposal_md = ? WHERE id = ?",
                     (proposal_text, strategy_id))
        # F53 — strategy committed; clear backward_session_id so any
        # future Backward on this same goal (e.g. cascade-reopen after
        # a sub-goal shelves) starts from a fresh session rather than
        # resuming a now-stale one talking about a superseded strategy.
        db.set_backward_session_id(conn, goal_id, None)
        conn.commit()

        return PipelineResult(outcome="success", proposal_md=proposal_text)

    except Exception as exc:
        # Cleanup: remove only this strategy's files (other strategies
        # untouched). Mark this strategy dead.
        for p in placed:
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        return _abort(
            "lake_build_error",
            diagnostics.annotate_failure_detail(str(exc)),
            proposal_text,
        )
