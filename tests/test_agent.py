"""agent.compile_context — Context.md assembly from DB + Manifest."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling import db
from Tooling.agent import compile_context
from Tooling.manifest import Manifest


def _empty_manifest(name: str = "p") -> Manifest:
    return Manifest(problem=name, statement="T")


def _seed_problem_and_goal(conn: sqlite3.Connection, **goal_kw: object) -> int:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at) VALUES (?, ?, ?)",
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


def test_context_includes_proved_goals_grep_pointer_when_some_proved(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """When ≥ 1 non-alias proved goal exists for the same problem
    (excluding the current goal itself), Context.md surfaces a count
    + grep target pointer — no inline candidate list, agent does its
    own grep / Read."""
    gid = _seed_problem_and_goal(conn)
    # Seed two proved sibling goals, one alias one canonical, plus one
    # open goal (none of which should be counted as the current one).
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
    assert "## Proved goals on this problem (grep entrypoint)" in text
    # Two non-alias proved goals counted (alias excluded)
    assert "2 proved goals" in text
    # Path target surfaces the per-problem proofs/ dir
    assert "Problems/p/proofs/L_<slug>.lean" in text
    # No inline list of candidates — agent runs its own grep
    assert "cross_sq_add_inner_sq" not in text
    assert "metric_triangle" not in text


# ---------------------------------------------------------------------
# F20 — Context.md surfaces resolved Mathlib signatures for names the
# agent has been confused about (errored on before, or were curated by
# Manifest as relevant)
# ---------------------------------------------------------------------

def test_context_sandbox_section_always_rendered_for_builder(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """P0-#4: Builder dispatch never passes strategy_id, but the
    universal Sandbox section (read-allowlist + framework file
    contracts) must still appear so Builder agents know which paths
    are allowed without permission prompts."""
    gid = _seed_problem_and_goal(conn)
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
    gid = _seed_problem_and_goal(conn)
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
    # Sandbox is universal — also present
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
    from Tooling import lemma_lookup

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
    from Tooling import lemma_lookup

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
    from Tooling import lemma_lookup

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


def test_context_includes_manifest_hint_names(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manifest.mathlib_hints feed the lookup batch even when no past
    error mentions them — the curated list is itself a query target."""
    from Tooling import lemma_lookup

    gid = _seed_problem_and_goal(conn)
    captured: list[list[str]] = []

    def _spy(names, ws):
        captured.append(list(names))
        return {}
    monkeypatch.setattr(lemma_lookup, "lookup_batch", _spy)

    mfst = Manifest(
        problem="p", statement="T",
        mathlib_hints=["Nat.factorial (Data/Nat/Factorial/Basic.lean:50)",
                       "ZMod.val_natCast"],
    )
    attempts_dir = tmp_path / ".attempts" / "pid-q"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    compile_context(conn, goal=goal, mfst=mfst, attempts_dir=attempts_dir)

    assert captured, "lookup_batch should be invoked when hints are present"
    assert "Nat.factorial" in captured[0]
    assert "ZMod.val_natCast" in captured[0]


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
