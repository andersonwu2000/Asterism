"""context.compile_context — Context.md assembly from DB + Manifest."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db
from Tooling.agent.context import compile_context
from Tooling.state.manifest import Manifest


def _empty_manifest(name: str = "p") -> Manifest:
    return Manifest(problem=name, statement="T")


def _seed_problem_and_goal(conn: sqlite3.Connection, **goal_kw: object) -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) VALUES (?, ?, ?, 1)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    return db.insert_goal(
        conn, problem="p", slug="main", lean_path="Problems/p/Root.lean",
        statement="T", origin="root", **goal_kw,
    )


def _record_pipeline(conn: sqlite3.Connection, pid: str, kind: str,
                     target_id: str, target_kind: str) -> None:
    conn.execute(
        "INSERT INTO pipelines (id, kind, target_id, target_kind, status,"
        " outcome, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, kind, target_id, target_kind, "failed", "failed",
         db.now(), db.now()),
    )
    conn.commit()


def test_context_includes_strategy_dead_attempts(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Verify failures must surface in the parent goal's Context so a
    fresh Backward agent doesn't repeat the broken combination pattern.

    F43: full inline rendering — Context.md carries the actual stderr
    + proposal_md, not a digest+pointer. Companion PAST_VERIFY_FAILURES.md is
    still written for forensics."""
    gid = _seed_problem_and_goal(conn)
    sid = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        created_by="pid-x",
        proposal_md="### My decomposition\n3 sub-goals via foo",
    )
    _record_pipeline(conn, "pid-x", "Verify", str(sid), "Strategy")
    db.record_dead_attempt(
        conn, target_id=sid, target_kind="Strategy", pipeline_id="pid-x",
        failure_reason="lake_build_error",
        failure_detail="error: type mismatch in have h_1",
    )

    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=tmp_path)
    text = out.read_text(encoding="utf-8")

    # Context.md (F43): full inline content, not a digest pointer
    assert "Sibling decompositions that failed Verify" in text
    assert "lake_build_error" in text
    assert "type mismatch in have h_1" in text
    assert "My decomposition" in text  # proposal_md inline

    # Companion file still written (forensics; F55 renamed)
    past_backward = (tmp_path / "PAST_VERIFY_FAILURES.md").read_text(encoding="utf-8")
    assert "My decomposition" in past_backward
    assert "type mismatch in have h_1" in past_backward


def test_context_no_strategy_section_when_clean(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    gid = _seed_problem_and_goal(conn)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "Sibling decompositions that failed Verify" not in text


# ---------------------------------------------------------------------
# F37 — dead-strategies anti-repetition hint for sequential Backward retry
# ---------------------------------------------------------------------

def test_context_includes_dead_strategies_with_subgoal_decomposition(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F37 — when a strategy has died (e.g. a sub-goal cascade-shelved
    it), the next Backward attempt must see its decomposition + sub-goal
    statuses so it doesn't re-propose the same shape."""
    gid = _seed_problem_and_goal(conn)
    sid = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        scratch_path="Problems/p/proofs/_strategy_s.lean",
        created_by="pid-x",
        proposal_md="### Decomp via foo + bar\n2 sub-goals.",
    )
    sub1 = db.insert_goal(
        conn, problem="p", slug="s1_sub_1",
        lean_path="Problems/p/proofs/L_s1_sub_1.lean",
        statement="∀ n, foo n = bar n",
        origin="backward", depth=1,
    )
    sub2 = db.insert_goal(
        conn, problem="p", slug="s1_sub_2",
        lean_path="Problems/p/proofs/L_s1_sub_2.lean",
        statement="∀ n, baz n",
        origin="backward", depth=1,
    )
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub1, position=0)
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub2, position=1)
    db.update_goal_status(conn, sub1, "shelved")  # the one that killed s
    db.update_strategy_status(conn, sid, "dead")

    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "Strategies whose decomposition died" in text
    assert "s1_sub_1" in text
    assert "(shelved)" in text
    assert "foo n = bar n" in text
    assert "s1_sub_2" in text


def test_context_omits_dead_strategies_when_none(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F37 — clean state: no dead strategies → section is absent."""
    gid = _seed_problem_and_goal(conn)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "Strategies whose decomposition died" not in text


def test_context_skips_half_baked_dead_strategies(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """F37 — recovery cleanup marks half-baked strategies dead with
    empty proposal_md and no sub-goals. Don't surface those as 'prior
    decompositions' — they carry no signal."""
    gid = _seed_problem_and_goal(conn)
    sid = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        created_by="pid-x", proposal_md="",  # half-baked
    )
    db.update_strategy_status(conn, sid, "dead")

    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "Strategies whose decomposition died" not in text


# ---------------------------------------------------------------------
# Phase 4 — proved-goals grep entrypoint section
# ---------------------------------------------------------------------

def test_context_omits_proved_goals_section_when_none_proved(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Fresh problem (only the current root goal exists, none proved
    yet) → section omitted entirely so Context.md isn't cluttered."""
    gid = _seed_problem_and_goal(conn)
    attempts_dir = tmp_path / ".attempts" / "pid-q"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=attempts_dir)
    text = out.read_text(encoding="utf-8")
    assert "Proved goals on this problem" not in text


def test_context_proved_goals_section_when_some_proved(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """≥ 1 non-alias proved goal → section surfaces total count + grep
    footer. When parent statement is too generic to extract keyword
    tokens (e.g. "T"), the curated top-3 list is empty; only count and
    grep pointer appear."""
    gid = _seed_problem_and_goal(conn)
    canon = db.insert_goal(
        conn, problem="p", slug="cross_sq_add_inner_sq",
        lean_path="Problems/p/proofs/L_cross_sq_add_inner_sq.lean",
        statement="T", origin="backward",
    )
    db.update_goal_status(conn, canon, "proved")
    other_proved = db.insert_goal(
        conn, problem="p", slug="metric_triangle",
        lean_path="Problems/p/proofs/L_metric_triangle.lean",
        statement="T", origin="backward",
    )
    db.update_goal_status(conn, other_proved, "proved")
    alias = db.insert_goal(
        conn, problem="p", slug="cross_sq_alias",
        lean_path="Problems/p/proofs/L_cross_sq_alias.lean",
        statement="T", origin="backward",
    )
    db.update_goal_status(conn, alias, "proved")
    db.set_alias_target(conn, alias, canon)

    attempts_dir = tmp_path / ".attempts" / "pid-q"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=attempts_dir)
    text = out.read_text(encoding="utf-8")
    # New section title with count
    assert "## Proved siblings on this problem (2 total)" in text
    # Grep footer always surfaces
    assert "Problems/p/proofs/L_<slug>.lean" in text
    # Parent stmt "T" has no extractable tokens → empty curated list →
    # candidate slugs NOT in text
    assert "cross_sq_add_inner_sq" not in text
    assert "metric_triangle" not in text


def test_context_proved_goals_curates_top3_by_keyword_overlap(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """When parent statement has real Lean keyword tokens, framework
    intersects with each proved sibling's statement and surfaces top 3
    by overlap score. Catches alpha-equivalent siblings whose names
    don't match the slug-pattern Tier 1 dedupe (e.g. agent named the
    new sub-goal completely differently from the existing proved one).

    Defense-in-depth (2026-05-26 post-Jordan): Jordan's `_alias`/`_2`
    duplicates are caught by Tier 1; this section catches "same
    statement, different name" duplicates by surfacing high-overlap
    siblings as the agent reads Context.md, before they decompose.
    """
    # Seed problem row first (FK constraint)
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, "
        "bootstrap_done) VALUES (?, ?, ?, 1)",
        ("p", "Problems/p/Manifest.md", db.now()),
    )
    # Parent statement mentions LinearMap, kernel, finrank, Module
    gid = db.insert_goal(
        conn, problem="p", slug="parent_target",
        lean_path="Problems/p/proofs/L_parent_target.lean",
        statement=(
            "(M : R →ₗ[K] R) (d : Module.Basis ι K R) :\n"
            "    Module.finrank K (LinearMap.ker M) = Fintype.card {t : Fin p // 0 < l t}"
        ),
        origin="backward",
    )

    # High overlap: shares LinearMap, kernel, finrank, Module, Basis
    g_high = db.insert_goal(
        conn, problem="p", slug="kernel_finrank_basis",
        lean_path="Problems/p/proofs/L_kernel_finrank_basis.lean",
        statement=(
            "(N : R →ₗ[K] R) (b : Module.Basis ι K R) :\n"
            "  Module.finrank K (LinearMap.ker N) = card_things"
        ),
        origin="backward",
    )
    db.update_goal_status(conn, g_high, "proved")

    # Medium overlap: shares LinearMap, Module
    g_med = db.insert_goal(
        conn, problem="p", slug="linmap_module_fact",
        lean_path="Problems/p/proofs/L_linmap_module_fact.lean",
        statement="(M : R →ₗ[K] R) : Module.id_thing M",
        origin="backward",
    )
    db.update_goal_status(conn, g_med, "proved")

    # Low overlap: no shared tokens
    g_low = db.insert_goal(
        conn, problem="p", slug="unrelated_lemma",
        lean_path="Problems/p/proofs/L_unrelated_lemma.lean",
        statement="(x y : Nat) : x + y = y + x",
        origin="backward",
    )
    db.update_goal_status(conn, g_low, "proved")

    attempts_dir = tmp_path / ".attempts" / "pid-q"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=attempts_dir)
    text = out.read_text(encoding="utf-8")

    # Section appears with total count
    assert "## Proved siblings on this problem (3 total)" in text
    # Top match by overlap — must appear inline
    assert "kernel_finrank_basis" in text
    # Medium match — also appears (top 3 cap, only 3 candidates total)
    assert "linmap_module_fact" in text
    # Low-overlap candidate has 0 shared tokens (`xy=yx` is short noise) —
    # excluded by min-overlap threshold
    # Allow it OR not based on token threshold — main assertion is order
    high_pos = text.find("kernel_finrank_basis")
    med_pos = text.find("linmap_module_fact")
    assert high_pos < med_pos, (
        "highest-overlap sibling must appear before lower-overlap ones")


# ---------------------------------------------------------------------
# F20 — Context.md surfaces resolved Mathlib signatures for names the
# agent has been confused about (errored on before, or were curated by
# Manifest as relevant)
# ---------------------------------------------------------------------

def test_context_sandbox_section_always_rendered_for_builder(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """The universal Sandbox section (read-allowlist + framework file
    contracts) must appear so Builder agents know which paths are
    allowed without permission prompts. Lives in BRIEF.md (cross-spawn
    stable); compile_context inlines it into Context.md."""
    from Tooling.state import brief
    gid = _seed_problem_and_goal(conn)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True, exist_ok=True)
    brief.write(tmp_path, _empty_manifest())
    attempts_dir = tmp_path / ".attempts" / "pid-bld"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=attempts_dir, kind="builder")
    text = out.read_text(encoding="utf-8")
    assert "## Sandbox" in text
    assert "Reads allowed" in text
    assert ".lake/packages/mathlib/Mathlib" in text
    # Strategy-naming section must NOT appear for Builder (no sub-goals)
    assert "## Strategy naming" not in text


def test_context_strategy_naming_only_for_backward_with_sid(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """The Backward-specific naming section appears only when a
    strategy_id is supplied (Backward dispatch path). Builder kind
    has no sub-goals so this section stays absent."""
    from Tooling.state import brief
    gid = _seed_problem_and_goal(conn)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True, exist_ok=True)
    brief.write(tmp_path, _empty_manifest())
    attempts_dir = tmp_path / ".attempts" / "pid-bw"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=attempts_dir,
                          strategy_id=42, kind="backward")
    text = out.read_text(encoding="utf-8")
    assert "## Strategy naming" in text
    assert "`s42`" in text
    # Strategy patch file + locked theorem name use sid_token.
    assert "_strategy_s42.lean" in text
    # Sub-goal slugs are agent-picked descriptive identifiers; the
    # section explains the rule rather than a fixed format.
    assert "new_<slug>.lean" in text
    assert "[a-z][a-z0-9_]*" in text
    # Auto-suffix on collision is documented so agent doesn't try to
    # be clever about uniqueness.
    assert "auto-suffix" in text
    # Sandbox is universal — also present (inlined from BRIEF.md)
    assert "## Sandbox" in text


def test_context_dead_strategies_visible_to_builder(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """P0-#4: Builder kind has show_verifies=False (no
    `## Sibling decompositions that failed Verify` section), so the
    dedupe filter that strips strategies-shown-in-verify-failures
    from `dead_strats` must NOT run for Builder — otherwise Builder
    silently loses the dead-strategy signal entirely."""
    gid = _seed_problem_and_goal(conn)
    # Seed a dead strategy on this goal with a committed sub
    sid = db.insert_strategy(
        conn, goal_id=gid, lean_path="Problems/p/Root.lean",
        created_by="pid-prior",
        proposal_md="dead strategy: split into A and B")
    db.update_strategy_status(conn, sid, "dead")
    sub = db.insert_goal(
        conn, problem="p", slug="ds_sub_1",
        lean_path="Problems/p/proofs/L_ds_sub_1.lean",
        statement="T", origin="backward", depth=1,
    )
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub, position=0)
    # And record a Verify dead_attempt so the dedupe set includes this sid
    _record_pipeline(conn, "pid-verify", "Verify", str(sid), "Strategy")
    db.record_dead_attempt(
        conn, target_id=sid, target_kind="Strategy",
        pipeline_id="pid-verify",
        failure_reason="lake_build_error",
        failure_detail="error: typeclass instance problem")
    # For Backward kind: dedupe should hide the dead strategy (verify
    # failures section already covers it).
    attempts_bw = tmp_path / ".attempts" / "pid-bw"
    attempts_bw.mkdir(parents=True)
    out_bw = compile_context(
        conn, goal=db.get_goal(conn, gid), mfst=_empty_manifest(),
        attempts_dir=attempts_bw, strategy_id=99, kind="backward")
    text_bw = out_bw.read_text(encoding="utf-8")
    assert "Sibling decompositions that failed Verify" in text_bw
    assert "Strategies whose decomposition died" not in text_bw  # deduped

    # For Builder kind: no verify-failures section, so dead strategy
    # MUST still be visible (regression: P0-#4 dedupe was unconditional).
    attempts_bld = tmp_path / ".attempts" / "pid-bld"
    attempts_bld.mkdir(parents=True)
    out_bld = compile_context(
        conn, goal=db.get_goal(conn, gid), mfst=_empty_manifest(),
        attempts_dir=attempts_bld, kind="builder")
    text_bld = out_bld.read_text(encoding="utf-8")
    assert "Sibling decompositions that failed Verify" not in text_bld
    assert "Strategies whose decomposition died" in text_bld


def test_context_emits_lemma_references_when_lookup_finds(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Past dead_attempt mentions `ZMod.val_natCast` in stderr →
    extract_lemma_names picks it → lookup_batch returns a found
    LemmaInfo → Context.md's `## Mathlib lemmas` section (the merged
    successor of the F20 `## Lemma references` block) lists it with
    its resolved signature."""
    from Tooling.knowledge import lemma_lookup

    gid = _seed_problem_and_goal(conn)
    _record_pipeline(conn, "pid-q", "Builder", str(gid), "Goal")
    db.record_dead_attempt(
        conn, target_id=gid, target_kind="Goal", pipeline_id="pid-q",
        failure_reason="lake_build_error",
        failure_detail=(
            "error: file.lean:7:2: Type mismatch on ZMod.val_natCast"
        ),
    )

    monkeypatch.setattr(lemma_lookup, "lookup_batch", lambda names, ws: {
        "ZMod.val_natCast": lemma_lookup.LemmaInfo(
            name="ZMod.val_natCast",
            signature="∀ (n a : ℕ), (↑a).val = a % n",
            found=True,
        ),
    })

    # Need a real attempts_dir layout: <workspace>/.attempts/<pid>/
    attempts_dir = tmp_path / ".attempts" / "pid-q"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=attempts_dir)
    text = out.read_text(encoding="utf-8")

    assert "## Mathlib lemmas" in text
    assert "ZMod.val_natCast" in text
    assert "(↑a).val = a % n" in text


def test_context_skips_lemma_references_when_lookup_finds_nothing(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If every name resolves to found=False, don't emit an empty
    section — the raw stderr already carries the error and a header
    with no bullets is just clutter."""
    from Tooling.knowledge import lemma_lookup

    gid = _seed_problem_and_goal(conn)
    _record_pipeline(conn, "pid-q", "Builder", str(gid), "Goal")
    db.record_dead_attempt(
        conn, target_id=gid, target_kind="Goal", pipeline_id="pid-q",
        failure_reason="lake_build_error",
        failure_detail="error: Unknown constant `Hallucinated.lemma`",
    )

    monkeypatch.setattr(lemma_lookup, "lookup_batch", lambda names, ws: {
        "Hallucinated.lemma": lemma_lookup.LemmaInfo(
            name="Hallucinated.lemma", signature="", found=False,
        ),
    })

    attempts_dir = tmp_path / ".attempts" / "pid-q"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=attempts_dir)
    text = out.read_text(encoding="utf-8")
    # No manifest hints + no resolved names → merged section absent.
    assert "## Mathlib lemmas" not in text


def test_context_lemma_lookup_failure_is_swallowed(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If lookup_batch crashes (e.g. no lake on PATH), Context.md must
    still be written. The agent can degrade gracefully without F20."""
    from Tooling.knowledge import lemma_lookup

    gid = _seed_problem_and_goal(conn)
    _record_pipeline(conn, "pid-q", "Builder", str(gid), "Goal")
    db.record_dead_attempt(
        conn, target_id=gid, target_kind="Goal", pipeline_id="pid-q",
        failure_reason="lake_build_error",
        failure_detail="error: Type mismatch on ZMod.val_natCast",
    )

    def _boom(names, ws):
        raise RuntimeError("lake unavailable")
    monkeypatch.setattr(lemma_lookup, "lookup_batch", _boom)

    attempts_dir = tmp_path / ".attempts" / "pid-q"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=attempts_dir)
    text = out.read_text(encoding="utf-8")
    # Other sections still present
    assert "Goal statement" in text


def test_brief_omits_retired_mathlib_hints(tmp_path: Path) -> None:
    """`## Lemma hints` / `## Mathlib lemmas` retired (target-1 pre-search
    replaces Manifest hints): BRIEF no longer renders mathlib hint names."""
    from Tooling.state import brief
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True, exist_ok=True)
    mfst = Manifest(
        problem="p", statement="T",
        mathlib_hints=["Nat.factorial (Data/Nat/Factorial/Basic.lean:50)",
                       "ZMod.val_natCast"],
    )
    out = brief.write(tmp_path, mfst)
    body = out.read_text(encoding="utf-8")
    assert "## Mathlib lemmas" not in body
    assert "Nat.factorial" not in body


def test_context_subgoal_includes_parent_strategy(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A backward-origin sub-goal should see its parent's slug, statement,
    and the originating strategy's PROPOSAL.md."""
    parent_gid = _seed_problem_and_goal(conn)
    sid = db.insert_strategy(
        conn, goal_id=parent_gid, lean_path="Problems/p/Root.lean",
        created_by="pid-y",
        proposal_md="parent decomposes into A, B, C",
    )
    sub_gid = db.insert_goal(
        conn, problem="p", slug="main_sub_1",
        lean_path="Problems/p/proofs/L_main_sub_1.lean",
        statement="A", origin="backward", depth=1,
    )
    db.link_subgoal(conn, strategy_id=sid, subgoal_id=sub_gid, position=0)

    sub_goal = db.get_goal(conn, sub_gid)
    out = compile_context(conn, goal=sub_goal, mfst=_empty_manifest(),
                          attempts_dir=tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "Parent goal & strategy" in text
    assert "main_sub_1" in text
    assert "main" in text  # parent slug
    assert "parent decomposes into A, B, C" in text


def test_workarea_exit_releases_gateway_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WorkArea.__exit__ must POST /release on the gateway session token
    persisted at `attempts/_gateway_session.token`. Without this hook,
    the LAST token of every pipeline (and the only token of one-shot
    pipelines) leaks — gateway accumulates SessionMetadata
    indefinitely (observed at /health: sessions_active=12 with
    workers_busy=0 after a run with 5-6 spawn fails on quota)."""
    from Tooling import agent
    from Tooling.lsp import lifecycle as gateway_lifecycle

    pid = "test-pid-release"
    captured: list[str] = []
    monkeypatch.setattr(gateway_lifecycle, "release_session",
                        lambda tok: captured.append(tok))

    with agent.WorkArea(tmp_path, pid) as wa:
        (wa.attempts / "_gateway_session.token").write_text(
            "deadbeef-token", encoding="utf-8")

    assert captured == ["deadbeef-token"]


def test_workarea_exit_no_release_when_no_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the pipeline never wrote a token (e.g. spawn-side
    _write_mcp_config crashed before /register completed), __exit__ must
    not call release."""
    from Tooling import agent
    from Tooling.lsp import lifecycle as gateway_lifecycle

    captured: list[str] = []
    monkeypatch.setattr(gateway_lifecycle, "release_session",
                        lambda tok: captured.append(tok))

    with agent.WorkArea(tmp_path, "pid-no-token"):
        pass

    assert captured == []


# ---------------------------------------------------------------------
# render_prompt_template — placeholder substitution
# ---------------------------------------------------------------------

def test_render_prompt_template_substitutes_timeout_min() -> None:
    """`{timeout_min}` reflects WORKER_TIMEOUT_SEC for body prompts and
    POSTMORTEM_TIMEOUT_SEC for postmortem prompts."""
    from Tooling.agent.runtime import (
        render_prompt_template, WORKER_TIMEOUT_SEC, POSTMORTEM_TIMEOUT_SEC,
    )
    body = render_prompt_template("budget {timeout_min}")
    assert body == f"budget {WORKER_TIMEOUT_SEC // 60}"
    pm = render_prompt_template("budget {timeout_min}", is_postmortem=True)
    assert pm == f"budget {POSTMORTEM_TIMEOUT_SEC // 60}"


def test_render_prompt_template_substitutes_interval_min(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`{interval_min}` reflects `strategist.interval_min`. Integer
    values render without a decimal; fractional values get one decimal."""
    from Tooling.agent.runtime import render_prompt_template
    monkeypatch.setenv("ASTERISM_STRATEGIST_INTERVAL_MIN", "60")
    assert render_prompt_template("every {interval_min}m") == "every 60m"
    monkeypatch.setenv("ASTERISM_STRATEGIST_INTERVAL_MIN", "30.5")
    assert render_prompt_template("every {interval_min}m") == "every 30.5m"


def test_render_prompt_template_noop_on_unknown_placeholder() -> None:
    """Unknown placeholders pass through unchanged; the helper only
    replaces names it knows."""
    from Tooling.agent.runtime import render_prompt_template
    text = render_prompt_template("keep {unknown_var} as-is")
    assert text == "keep {unknown_var} as-is"


# ---------------------------------------------------------------------
# task #7 — context/token telemetry
# ---------------------------------------------------------------------

def test_write_context_stats(tmp_path, capsys):
    import json
    from Tooling.agent import context as ctx
    ctx.write_context_stats(
        tmp_path, label="builder g7",
        names=["brief", "empty", "history"],
        sections=[["## Brief", "line"], [], ["## H", "a", "b", "c"]])
    data = json.loads((tmp_path / "_context_stats.json").read_text(
        encoding="utf-8"))
    assert data["label"] == "builder g7"
    names = {s["section"] for s in data["sections"]}
    assert names == {"brief", "history"}          # empty section omitted
    assert data["total_bytes"] == sum(s["bytes"] for s in data["sections"])
    out = capsys.readouterr().out
    assert "[context] builder g7" in out


def test_stream_parser_accumulates_usage():
    import json
    from Tooling.llm.stream_parser import StreamParser
    p = StreamParser()

    def ev(event):
        p.feed_line(json.dumps({"type": "stream_event", "event": event}))
    ev({"type": "message_start",
        "message": {"usage": {"input_tokens": 100,
                              "cache_read_input_tokens": 500,
                              "cache_creation_input_tokens": 20}}})
    ev({"type": "message_delta", "delta": {"stop_reason": None},
        "usage": {"output_tokens": 40}})
    ev({"type": "message_delta", "delta": {"stop_reason": "end_turn"},
        "usage": {"output_tokens": 90}})          # cumulative within turn
    ev({"type": "message_stop"})
    ev({"type": "message_start",
        "message": {"usage": {"input_tokens": 10}}})
    ev({"type": "message_delta", "delta": {},
        "usage": {"output_tokens": 5}})           # turn still in flight
    u = p.usage()
    assert u["input_tokens"] == 110
    assert u["cache_read_input_tokens"] == 500
    assert u["cache_creation_input_tokens"] == 20
    assert u["output_tokens"] == 95               # 90 final + 5 in-flight
    assert u["turns"] == 1
