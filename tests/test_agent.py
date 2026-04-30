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
        statement="T", origin="root", difficulty=4, **goal_kw,
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
    """Verify failures should surface in the parent goal's Context so a
    fresh Backward agent doesn't repeat the broken combination pattern."""
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

    assert "Past decompositions that failed Verify" in text
    assert "lake_build_error" in text
    assert "type mismatch" in text
    assert "My decomposition" in text


def test_context_no_strategy_section_when_clean(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    gid = _seed_problem_and_goal(conn)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=tmp_path)
    text = out.read_text(encoding="utf-8")
    assert "Past decompositions that failed Verify" not in text


# ---------------------------------------------------------------------
# F22 — Context.md surfaces playbook entries
# ---------------------------------------------------------------------

def test_context_includes_playbook_when_present(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    gid = _seed_problem_and_goal(conn)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "playbook.md").write_text(
        "- **goal foo**: use trick X\n", encoding="utf-8")

    attempts_dir = tmp_path / ".attempts" / "pid-q"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=attempts_dir)
    text = out.read_text(encoding="utf-8")
    assert "## Past wins on this problem (playbook)" in text
    assert "use trick X" in text


def test_context_omits_playbook_when_missing(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    gid = _seed_problem_and_goal(conn)
    attempts_dir = tmp_path / ".attempts" / "pid-q"
    attempts_dir.mkdir(parents=True)
    goal = db.get_goal(conn, gid)
    out = compile_context(conn, goal=goal, mfst=_empty_manifest(),
                          attempts_dir=attempts_dir)
    text = out.read_text(encoding="utf-8")
    assert "Past wins on this problem" not in text


# ---------------------------------------------------------------------
# F20 — Context.md surfaces resolved Mathlib signatures for names the
# agent has been confused about (errored on before, or were curated by
# Manifest as relevant)
# ---------------------------------------------------------------------

def test_context_emits_lemma_references_when_lookup_finds(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Past dead_attempt mentions `ZMod.val_natCast` in stderr →
    extract_lemma_names picks it → lookup_batch returns a found
    LemmaInfo → Context.md gets a `## Lemma references` bullet."""
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

    assert "## Lemma references" in text
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
    assert "## Lemma references" not in text


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
        statement="A", origin="backward", difficulty=3, depth=1,
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
