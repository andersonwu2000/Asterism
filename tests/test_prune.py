"""prune library: winning_chain walk + prune_problem behavior."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.state import db
from Tooling.quality import prune


def _seed_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done) VALUES (?, ?, ?, 1)",
        (name, f"Problems/{name}/Manifest.md", db.now()),
    )


def _seed_root(conn: sqlite3.Connection, name: str = "p",
               status: str = "proved", *, verified: bool = True) -> int:
    """Seed a root goal. By default sets integrity_verified=1 so the
    post-2026-05-26 prune integrity gate (added after Jordan disaster)
    doesn't refuse on every existing test. Tests that exercise the
    gate-refuse path explicitly pass `verified=False`."""
    gid = db.insert_goal(
        conn, problem=name, slug="main",
        lean_path=f"Problems/{name}/Root.lean",
        statement="T", origin="root",
    )
    db.update_goal_status(conn, gid, status)
    if verified and status == "proved":
        db.set_integrity_verified(conn, gid)
    return gid


def _seed_strategy(conn: sqlite3.Connection, *, goal_id: int, sid_label: str,
                   problem: str = "p", status: str = "succeeded") -> int:
    sid = db.insert_strategy(
        conn, goal_id=goal_id,
        lean_path=f"Problems/{problem}/Root.lean",
        scratch_path=f"Problems/{problem}/proofs/_strategy_{sid_label}.lean",
        created_by="pid-x",
    )
    if status != "proposed":
        db.update_strategy_status(conn, sid, status)
    return sid


def _seed_subgoal(conn: sqlite3.Connection, *, problem: str, slug: str,
                  status: str = "proved") -> int:
    sub = db.insert_goal(
        conn, problem=problem, slug=slug,
        lean_path=f"Problems/{problem}/proofs/L_{slug}.lean",
        statement="T", origin="backward", depth=1,
    )
    if status != "open":
        db.update_goal_status(conn, sub, status)
    return sub


# ---------------------------------------------------------------------
# winning_chain
# ---------------------------------------------------------------------

def test_winning_chain_one_strategy(conn: sqlite3.Connection) -> None:
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub1 = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    sub2 = _seed_subgoal(conn, problem="p", slug="s1_main_sub_2")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub1, position=0)
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub2, position=1)

    keep = prune.winning_chain(conn, "p")
    assert keep == {
        "Problems/p/Root.lean",
        "Problems/p/proofs/_strategy_s1.lean",
        "Problems/p/proofs/L_s1_main_sub_1.lean",
        "Problems/p/proofs/L_s1_main_sub_2.lean",
    }


def test_winning_chain_skips_superseded_strategies(
    conn: sqlite3.Connection,
) -> None:
    """Only the 'succeeded' strategy of a goal contributes to the chain;
    'superseded' / 'dead' OR siblings and their sub-goals are excluded."""
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1", status="succeeded")
    loser = _seed_strategy(conn, goal_id=root, sid_label="s2",
                           status="superseded")
    win_sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    loser_sub = _seed_subgoal(conn, problem="p", slug="s2_main_sub_1",
                              status="open")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=win_sub, position=0)
    db.link_subgoal(conn, strategy_id=loser, subgoal_id=loser_sub, position=0)

    keep = prune.winning_chain(conn, "p")
    assert "Problems/p/proofs/_strategy_s1.lean" in keep
    assert "Problems/p/proofs/L_s1_main_sub_1.lean" in keep
    assert "Problems/p/proofs/_strategy_s2.lean" not in keep
    assert "Problems/p/proofs/L_s2_main_sub_1.lean" not in keep


def test_winning_chain_recursive_through_nested_strategies(
    conn: sqlite3.Connection,
) -> None:
    """Sub-goal proved via its own succeeded sub-strategy is included."""
    _seed_problem(conn)
    root = _seed_root(conn)
    s_root = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=s_root, subgoal_id=sub, position=0)

    s_sub = _seed_strategy(conn, goal_id=sub, sid_label="s5", problem="p")
    leaf = _seed_subgoal(conn, problem="p", slug="s5_s1_main_sub_1_sub_1")
    db.link_subgoal(conn, strategy_id=s_sub, subgoal_id=leaf, position=0)

    keep = prune.winning_chain(conn, "p")
    assert "Problems/p/proofs/_strategy_s5.lean" in keep
    assert "Problems/p/proofs/L_s5_s1_main_sub_1_sub_1.lean" in keep


def test_winning_chain_empty_when_root_not_proved(
    conn: sqlite3.Connection,
) -> None:
    _seed_problem(conn)
    _seed_root(conn, status="open")
    assert prune.winning_chain(conn, "p") == set()


# ---------------------------------------------------------------------
# prune_problem
# ---------------------------------------------------------------------

def _build_proofs_tree(workspace: Path, problem: str,
                       filenames: list[str]) -> dict[str, Path]:
    proofs = workspace / "Problems" / problem / "proofs"
    proofs.mkdir(parents=True, exist_ok=True)
    paths = {}
    for fn in filenames:
        p = proofs / fn
        p.write_text("-- placeholder\n", encoding="utf-8")
        paths[fn] = p
    # Also seed Root.lean and Defs.lean above proofs/, to confirm prune
    # never touches them.
    (workspace / "Problems" / problem / "Root.lean").write_text(
        "-- root\n", encoding="utf-8")
    (workspace / "Problems" / problem / "Defs.lean").write_text(
        "-- defs\n", encoding="utf-8")
    return paths


def test_prune_problem_removes_orphans_keeps_winners(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub, position=0)

    files = _build_proofs_tree(tmp_path, "p", [
        "_strategy_s1.lean",          # winner scratch
        "L_s1_main_sub_1.lean",       # winner sub-goal
        "_strategy_s2.lean",          # orphan (no row in DB at all)
        "L_orphan_sub.lean",          # orphan
    ])

    removed = prune.prune_problem(conn, tmp_path, "p")
    removed_names = {p.name for p in removed}
    assert removed_names == {"_strategy_s2.lean", "L_orphan_sub.lean"}
    assert files["_strategy_s1.lean"].exists()
    assert files["L_s1_main_sub_1.lean"].exists()
    assert not files["_strategy_s2.lean"].exists()
    # Defs.lean and Root.lean (above proofs/) are untouched
    assert (tmp_path / "Problems/p/Root.lean").exists()
    assert (tmp_path / "Problems/p/Defs.lean").exists()


def test_prune_problem_idempotent(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub, position=0)
    _build_proofs_tree(tmp_path, "p",
                       ["_strategy_s1.lean", "L_s1_main_sub_1.lean",
                        "_strategy_s2.lean"])

    first = prune.prune_problem(conn, tmp_path, "p")
    second = prune.prune_problem(conn, tmp_path, "p")
    assert len(first) == 1
    assert second == []


def test_prune_problem_noop_when_root_not_proved(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    _seed_problem(conn)
    _seed_root(conn, status="attempting")
    _build_proofs_tree(tmp_path, "p", ["L_anything.lean"])

    removed = prune.prune_problem(conn, tmp_path, "p")
    assert removed == []
    assert (tmp_path / "Problems/p/proofs/L_anything.lean").exists()


def test_prune_problem_dry_run_does_not_delete(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub, position=0)
    files = _build_proofs_tree(tmp_path, "p",
                               ["_strategy_s1.lean", "L_s1_main_sub_1.lean",
                                "_strategy_s99.lean"])

    removed = prune.prune_problem(conn, tmp_path, "p", dry_run=True)
    assert {p.name for p in removed} == {"_strategy_s99.lean"}
    # File still on disk after dry-run
    assert files["_strategy_s99.lean"].exists()


def test_prune_problem_keeps_files_reached_only_via_import(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Wrapper-cites-sibling anti-pattern: the winning chain contains
    `_strategy_s1.lean` + `L_s1_main_sub_1.lean`, but the sub-goal
    wrapper's body imports `L_sibling_lemma.lean` (a separate proved
    lemma that the wrapper cites by short name, bypassing the
    strategy_subgoals DB edge via the auto-import helper). DB-only
    `winning_chain` doesn't see this — without import-aware expansion
    prune would delete L_sibling_lemma and the next cold lake build
    fails on `bad import`. Residue_thm 2026-05-21 incident shape.
    """
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub, position=0)

    # `L_sibling_lemma.lean` is a real on-disk file (some proved sibling
    # lemma) that the wrapper imports + cites by short name.
    files = _build_proofs_tree(tmp_path, "p", [
        "_strategy_s1.lean",
        "L_s1_main_sub_1.lean",
        "L_sibling_lemma.lean",   # imported by wrapper, NOT in DB chain
        "L_truly_orphan.lean",    # actually orphan, nobody imports
    ])
    # Wrapper body cites + imports a sibling lemma file.
    files["L_s1_main_sub_1.lean"].write_text(
        "import Mathlib\n"
        "import Problems.p.proofs.L_sibling_lemma\n"
        "namespace Problems.p\n"
        "theorem s1_main_sub_1 := sibling_lemma\n"
        "end Problems.p\n",
        encoding="utf-8",
    )
    # Also seed Root.lean with a realistic import of the winning strat,
    # to confirm the Root-seeded walk reaches strategy files.
    (tmp_path / "Problems/p/Root.lean").write_text(
        "import Problems.p.proofs._strategy_s1\n", encoding="utf-8")

    removed = prune.prune_problem(conn, tmp_path, "p")
    removed_names = {p.name for p in removed}

    # The DB-invisible-but-imported sibling stays; the truly-orphan goes.
    assert "L_sibling_lemma.lean" not in removed_names, (
        "import-walked sibling must NOT be pruned")
    assert "L_truly_orphan.lean" in removed_names, (
        "files no one imports / no DB edge MUST be pruned")
    assert files["L_sibling_lemma.lean"].exists()
    assert not files["L_truly_orphan.lean"].exists()


def test_prune_problem_import_walk_handles_dotted_problem_name(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Domain.slug naming convention (e.g. LinearAlgebra.jordan_normal_form,
    Minif2f.aime_1997_p11) produces import paths like
    `Problems.LinearAlgebra.jordan_normal_form.proofs.L_xxx` with multiple
    segments between Problems and proofs. The pre-fix `_IMPORT_RE` only
    allowed one segment, silently failing to find any imports under the
    new convention.

    Combined with a Backward leaf-bypass strategy (strategy_subgoals
    table empty; chain reachable only via .lean imports — by design,
    `_expand_keep_via_imports` is the compensating mechanism),
    jordan_normal_form 2026-05-25 had its entire proof tree (122 sub-goal
    files) deleted as orphans, leaving the framework with status='proved'
    in DB but no on-disk artifacts to lake build.
    """
    name = "LinearAlgebra.jordan_normal_form"
    # `db.problem_dir` splits dots into path segments
    # (Problems/LinearAlgebra/jordan_normal_form/). Build DB rows + on-disk
    # paths using that same shape so they match the framework's resolution
    # at prune time.
    pdir_rel = "Problems/LinearAlgebra/jordan_normal_form"

    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at, bootstrap_done)"
        " VALUES (?, ?, ?, 1)",
        (name, f"{pdir_rel}/Manifest.md", db.now()),
    )
    root = db.insert_goal(
        conn, problem=name, slug="main",
        lean_path=f"{pdir_rel}/Root.lean",
        statement="T", origin="root",
    )
    db.update_goal_status(conn, root, "proved")
    db.set_integrity_verified(conn, root)
    win = db.insert_strategy(
        conn, goal_id=root,
        lean_path=f"{pdir_rel}/Root.lean",
        scratch_path=f"{pdir_rel}/proofs/_strategy_s1.lean",
        created_by="pid-x",
    )
    db.update_strategy_status(conn, win, "succeeded")
    # Strategy_subgoals deliberately empty — mimics Backward leaf-bypass.
    # The strategy file cites a sibling proved lemma via .lean import.
    # cited goal is in DB (proved) but NOT linked via strategy_subgoals;
    # reachable from the winning strategy only at the .lean import level.
    cited = db.insert_goal(
        conn, problem=name, slug="cited_lemma",
        lean_path=f"{pdir_rel}/proofs/L_cited_lemma.lean",
        statement="T", origin="backward", depth=1,
    )
    db.update_goal_status(conn, cited, "proved")

    # Build proofs/ at the same Path(*split('.')) shape db.problem_dir uses.
    proofs = tmp_path / pdir_rel / "proofs"
    proofs.mkdir(parents=True, exist_ok=True)
    strategy_file = proofs / "_strategy_s1.lean"
    cited_file = proofs / "L_cited_lemma.lean"
    orphan_file = proofs / "L_truly_orphan.lean"
    for p in (strategy_file, cited_file, orphan_file):
        p.write_text("-- placeholder\n", encoding="utf-8")
    strategy_file.write_text(
        "import Mathlib\n"
        f"import Problems.{name}.proofs.L_cited_lemma\n"
        f"namespace Problems.{name}\n"
        "theorem s1 : True := cited_lemma\n"
        f"end Problems.{name}\n",
        encoding="utf-8",
    )
    root_lean = tmp_path / pdir_rel / "Root.lean"
    root_lean.write_text(
        f"import Problems.{name}.proofs._strategy_s1\n", encoding="utf-8")

    removed = prune.prune_problem(conn, tmp_path, name)
    removed_names = {p.name for p in removed}

    assert "L_cited_lemma.lean" not in removed_names, (
        f"Domain.slug-named problem's leaf-bypass cite must NOT be pruned; "
        f"removed={removed_names}")
    assert "L_truly_orphan.lean" in removed_names, (
        f"truly orphan file MUST be pruned; removed={removed_names}")
    assert "_strategy_s1.lean" not in removed_names, (
        f"winning strategy file MUST NOT be pruned; removed={removed_names}")
    assert cited_file.exists()
    assert not orphan_file.exists()


def test_prune_problem_import_walk_handles_cycles(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Two wrappers importing each other (a sloppy pattern, but legal)
    must not infinite-loop the import-walk."""
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub, position=0)
    files = _build_proofs_tree(tmp_path, "p", [
        "_strategy_s1.lean",
        "L_s1_main_sub_1.lean",
        "L_cycle_a.lean",
        "L_cycle_b.lean",
    ])
    files["L_s1_main_sub_1.lean"].write_text(
        "import Problems.p.proofs.L_cycle_a\n", encoding="utf-8")
    files["L_cycle_a.lean"].write_text(
        "import Problems.p.proofs.L_cycle_b\n", encoding="utf-8")
    files["L_cycle_b.lean"].write_text(
        "import Problems.p.proofs.L_cycle_a\n", encoding="utf-8")

    removed = prune.prune_problem(conn, tmp_path, "p")
    assert files["L_cycle_a.lean"].exists()
    assert files["L_cycle_b.lean"].exists()


def test_prune_problem_import_walk_ignores_external_imports(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """`import Mathlib` and cross-problem imports must not enlarge
    the keep set (they aren't prune targets anyway, but the regex
    should filter them so the walk stays cheap and clean)."""
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub, position=0)
    files = _build_proofs_tree(tmp_path, "p", [
        "_strategy_s1.lean",
        "L_s1_main_sub_1.lean",
        "L_unrelated.lean",
    ])
    files["L_s1_main_sub_1.lean"].write_text(
        "import Mathlib\n"
        "import Problems.p.Defs\n"
        "import Problems.q.proofs.L_qthing\n"   # cross-problem; ignore
        "namespace Problems.p\nend Problems.p\n",
        encoding="utf-8",
    )

    removed = prune.prune_problem(conn, tmp_path, "p")
    assert "L_unrelated.lean" in {p.name for p in removed}


# ---------------------------------------------------------------------
# reconcile_proved_goals (E6: file/DB drift repair)
# ---------------------------------------------------------------------

def _seed_drifted_subgoal(conn: sqlite3.Connection, *, problem: str,
                           parent_slug: str, win_sid: int, lose_sid: int,
                           statement: str = "T") -> Path:
    """Seed a sub-goal whose lean_path imports BOTH the winning and the
    losing strategies' scratch (last-write-wins from a Verify race).
    Returns the absolute parent file path (caller has tmp_path)."""
    raise NotImplementedError  # placeholder (test uses inline construction)


def test_reconcile_repairs_drifted_parent_lean_path(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Simulate the compactness goal-4 race: parent file imports both
    s7 and s14 and aliases to s14, but DB says s7 is the succeeded
    strategy. Reconcile must rewrite to canonical s7-only form."""
    _seed_problem(conn)
    parent_gid = _seed_root(conn)
    # Two strategies, only s7 is succeeded
    sid7 = _seed_strategy(conn, goal_id=parent_gid, sid_label="s7",
                           status="succeeded")
    sid14 = _seed_strategy(conn, goal_id=parent_gid, sid_label="s14",
                            status="superseded")
    # Override scratch_path to use the actual sid for the canonical form
    db.update_strategy_scratch_path(
        conn, sid7,
        f"Problems/p/proofs/_strategy_s{sid7}.lean")
    db.update_strategy_scratch_path(
        conn, sid14,
        f"Problems/p/proofs/_strategy_s{sid14}.lean")

    # Build the proofs tree with both scratch files present
    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / f"_strategy_s{sid7}.lean").write_text("-- winner\n")
    (proofs / f"_strategy_s{sid14}.lean").write_text("-- loser\n")

    # The parent file is at "Problems/p/Root.lean" per _seed_root;
    # write the drifted content imitating last-write-wins from s14.
    parent = tmp_path / "Problems/p/Root.lean"
    parent.parent.mkdir(parents=True, exist_ok=True)
    drifted = (
        f"import Mathlib\n"
        f"import Problems.p.proofs._strategy_s{sid7}\n"
        f"import Problems.p.proofs._strategy_s{sid14}\n\n"
        f"namespace Problems.p\n\n"
        f"theorem main : T := s{sid14}_main\n\n"
        f"end Problems.p\n"
    )
    parent.write_text(drifted, encoding="utf-8")

    repaired = prune.reconcile_proved_goals(conn, tmp_path, "p")
    assert parent in repaired

    new_content = parent.read_text(encoding="utf-8")
    assert f"import Problems.p.proofs._strategy_s{sid7}" in new_content
    assert f"import Problems.p.proofs._strategy_s{sid14}" not in new_content
    # P0-#2: canonical form is a `def` re-export so Lean copies the
    # type from the strategy theorem (preserving binders). The pre-
    # P0-#2 form `theorem main : T := s7` stripped binders and broke
    # any non-trivially-bound goal at lake build.
    assert f"def main := @Problems.p.s{sid7}" in new_content
    assert "theorem main :" not in new_content


def test_reconcile_idempotent(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Already-canonical parent file is left untouched on second call."""
    _seed_problem(conn)
    root = _seed_root(conn)
    sid = _seed_strategy(conn, goal_id=root, sid_label="s1",
                         status="succeeded")
    db.update_strategy_scratch_path(
        conn, sid, f"Problems/p/proofs/_strategy_s{sid}.lean")

    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / f"_strategy_s{sid}.lean").write_text("-- ok\n")
    parent = tmp_path / "Problems/p/Root.lean"
    parent.parent.mkdir(parents=True, exist_ok=True)
    # Pre-seed a drifted parent (extra import) to verify first-pass repair.
    parent.write_text(
        f"import Mathlib\nimport Problems.p.proofs._strategy_s{sid}\n"
        f"import Problems.p.proofs._strategy_s99\n\n"
        f"namespace Problems.p\n\n"
        f"theorem main : T := s{sid}_main\n\n"
        f"end Problems.p\n",
        encoding="utf-8",
    )

    first = prune.reconcile_proved_goals(conn, tmp_path, "p")
    assert parent in first

    second = prune.reconcile_proved_goals(conn, tmp_path, "p")
    assert second == []  # already canonical


def test_reconcile_skips_goals_proved_by_builder(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """A goal proved directly by Builder has no 'succeeded' strategy;
    reconcile must skip it (no scratch to alias from)."""
    _seed_problem(conn)
    _seed_root(conn)  # root proved, but no strategy
    repaired = prune.reconcile_proved_goals(conn, tmp_path, "p")
    assert repaired == []


def test_reconcile_idempotent_on_promote_output_with_annotation(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """SG 2026-05-19 regression: `promote_to_alias` (Verify time)
    prepends a `--` comment block from `strategies.proposal_md` for
    human readers + agent grep. Pre-fix `_canonical_alias_content`
    dropped the annotation, so reconcile re-wrote every Verify-promoted
    file → 13/13 strategy-proved SG goals invalidated their oleans,
    integrity probe blocked ~8min on the 180s budget.

    Reconcile must treat Verify's annotated output as already canonical.
    """
    _seed_problem(conn)
    root = _seed_root(conn)
    sid = _seed_strategy(conn, goal_id=root, sid_label="s1",
                         status="succeeded")
    db.update_strategy_scratch_path(
        conn, sid, f"Problems/p/proofs/_strategy_s{sid}.lean")
    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / f"_strategy_s{sid}.lean").write_text("-- ok\n")
    parent = tmp_path / "Problems/p/Root.lean"
    parent.parent.mkdir(parents=True, exist_ok=True)
    # Exactly what `promote_to_alias` would write for a strategy
    # whose proposal_md starts with a rationale comment block.
    parent.write_text(
        "-- Strategy: cover the main case by reduction to s1.\n"
        "-- Sub-claim: this reduction preserves the binder shape.\n"
        f"import Mathlib\nimport Problems.p.proofs._strategy_s{sid}\n\n"
        f"namespace Problems.p\n\n"
        f"def main := @Problems.p.s{sid}\n\n"
        f"end Problems.p\n",
        encoding="utf-8",
    )
    before = parent.read_text(encoding="utf-8")
    repaired = prune.reconcile_proved_goals(conn, tmp_path, "p")
    assert repaired == []  # annotation-preserving canonical → no rewrite
    assert parent.read_text(encoding="utf-8") == before


def test_reconcile_repairs_drift_but_keeps_annotation(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Annotation preservation must compose with sibling-import
    cleanup: stale `_strategy_s*` import dropped, but `--` rationale
    block kept."""
    _seed_problem(conn)
    root = _seed_root(conn)
    winner = _seed_strategy(conn, goal_id=root, sid_label="s1",
                            status="succeeded")
    loser = _seed_strategy(conn, goal_id=root, sid_label="s2",
                           status="superseded")
    db.update_strategy_scratch_path(
        conn, winner, f"Problems/p/proofs/_strategy_s{winner}.lean")
    db.update_strategy_scratch_path(
        conn, loser, f"Problems/p/proofs/_strategy_s{loser}.lean")
    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / f"_strategy_s{winner}.lean").write_text("-- ok\n")
    (proofs / f"_strategy_s{loser}.lean").write_text("-- stale\n")
    parent = tmp_path / "Problems/p/Root.lean"
    parent.parent.mkdir(parents=True, exist_ok=True)
    parent.write_text(
        "-- Strategy: pick winner.\n"
        f"import Mathlib\n"
        f"import Problems.p.proofs._strategy_s{winner}\n"
        f"import Problems.p.proofs._strategy_s{loser}\n\n"
        f"namespace Problems.p\n\n"
        f"def main := @Problems.p.s{winner}\n\n"
        f"end Problems.p\n",
        encoding="utf-8",
    )
    repaired = prune.reconcile_proved_goals(conn, tmp_path, "p")
    assert parent in repaired
    new_content = parent.read_text(encoding="utf-8")
    assert "-- Strategy: pick winner." in new_content
    assert f"_strategy_s{winner}" in new_content
    assert f"_strategy_s{loser}" not in new_content


def test_reconcile_idempotent_on_f52_def_alias_form(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """P0-#2 regression: Verify Step 2 writes parent in def-alias
    form (`def slug := @ns.sX`) per F52. The end-of-run reconcile
    must NOT keep flipping that file back to a different shape every
    pass — that would silently undo the binder-preservation fix.
    """
    _seed_problem(conn)
    root = _seed_root(conn)
    sid = _seed_strategy(conn, goal_id=root, sid_label="s1",
                         status="succeeded")
    db.update_strategy_scratch_path(
        conn, sid, f"Problems/p/proofs/_strategy_s{sid}.lean")
    proofs = tmp_path / "Problems" / "p" / "proofs"
    proofs.mkdir(parents=True)
    (proofs / f"_strategy_s{sid}.lean").write_text("-- ok\n")
    parent = tmp_path / "Problems/p/Root.lean"
    parent.parent.mkdir(parents=True, exist_ok=True)
    # Pre-seed the parent already in F52 def-alias form (i.e. exactly
    # what _promote_to_alias would write).
    parent.write_text(
        f"import Mathlib\nimport Problems.p.proofs._strategy_s{sid}\n\n"
        f"namespace Problems.p\n\n"
        f"def main := @Problems.p.s{sid}\n\n"
        f"end Problems.p\n",
        encoding="utf-8",
    )
    before = parent.read_text(encoding="utf-8")
    repaired = prune.reconcile_proved_goals(conn, tmp_path, "p")
    assert repaired == []  # already canonical → no rewrite
    assert parent.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------
# F42 — winning_chain follows alias_target_id so orphan canonicals stay
# ---------------------------------------------------------------------

def test_winning_chain_keeps_alias_canonical(
    conn: sqlite3.Connection,
) -> None:
    """An alive alias's lean file imports its canonical's lean file.
    winning_chain must include the canonical so prune doesn't delete
    its file (the alias's lake build would then break)."""
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    # The winner's sub is itself an alias to an orphan canonical
    alias = _seed_subgoal(conn, problem="p", slug="s1_sub_alias")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=alias, position=0)

    # Orphan canonical from a prior dead strategy on a different parent
    other_parent = db.insert_goal(
        conn, problem="p", slug="other_parent",
        lean_path="Problems/p/proofs/L_other_parent.lean",
        statement="P", origin="backward", depth=1,
    )
    s_dead = db.insert_strategy(
        conn, goal_id=other_parent,
        lean_path="Problems/p/proofs/L_other_parent.lean",
        scratch_path="Problems/p/proofs/_strategy_dead.lean",
        created_by="pid-dead",
    )
    db.update_strategy_status(conn, s_dead, "dead")
    canonical = db.insert_goal(
        conn, problem="p", slug="canonical",
        lean_path="Problems/p/proofs/L_canonical.lean",
        statement="X", origin="backward", depth=2,
    )
    db.update_goal_status(conn, canonical, "proved")
    db.link_subgoal(conn, strategy_id=s_dead, subgoal_id=canonical,
                    position=0)
    # Winner's alias points at the orphan canonical
    db.set_alias_target(conn, alias, canonical)

    keep = prune.winning_chain(conn, "p")
    # Without F42 the canonical's file would be missing → alias broken.
    assert "Problems/p/proofs/L_canonical.lean" in keep
    assert "Problems/p/proofs/L_s1_sub_alias.lean" in keep


def test_winning_chain_handles_alias_chain_without_loop(
    conn: sqlite3.Connection,
) -> None:
    """alias→alias→concrete shouldn't happen in production (orphan
    pool excludes already-alias goals), but if it did, walk's visited-
    set must prevent infinite recursion."""
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    a = _seed_subgoal(conn, problem="p", slug="alias_a")
    b = _seed_subgoal(conn, problem="p", slug="alias_b")
    c = _seed_subgoal(conn, problem="p", slug="concrete")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=a, position=0)
    db.set_alias_target(conn, a, b)
    db.set_alias_target(conn, b, c)

    keep = prune.winning_chain(conn, "p")
    # All three files retained; no infinite loop
    for slug in ("alias_a", "alias_b", "concrete"):
        assert f"Problems/p/proofs/L_{slug}.lean" in keep


def test_prune_problem_moves_to_backup_dir_not_unlinks(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Defense-in-depth (2026-05-26 post-Jordan): prune must MOVE orphan
    files to a timestamped `.pruned/<ts>/` directory rather than
    `unlink`, so the operator can restore from disk if a cold build
    breaks post-prune. The Jordan 2026-05-25 wipe (~235 unrecoverable
    files) motivated this — even with all known logic bugs fixed, the
    delete step itself must be reversible."""
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub, position=0)
    files = _build_proofs_tree(tmp_path, "p", [
        "_strategy_s1.lean", "L_s1_main_sub_1.lean",
        "_strategy_s99.lean",   # orphan
    ])
    proofs_dir = tmp_path / "Problems/p/proofs"
    pruned_root = proofs_dir.parent / ".pruned"

    removed = prune.prune_problem(conn, tmp_path, "p")
    assert {p.name for p in removed} == {"_strategy_s99.lean"}
    # Source gone from proofs/
    assert not files["_strategy_s99.lean"].exists()
    # But preserved under .pruned/<ts>/
    assert pruned_root.exists(), "prune must create .pruned/ backup dir"
    ts_dirs = list(pruned_root.iterdir())
    assert len(ts_dirs) == 1, "exactly one timestamp dir expected per prune run"
    assert (ts_dirs[0] / "_strategy_s99.lean").exists(), (
        "orphan file must be moved (not unlinked) into .pruned/<ts>/")
    # Dry-run should NOT create the backup dir
    pruned_root_again = pruned_root  # capture for later assertion


def test_prune_problem_dry_run_does_not_create_backup_dir(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    _build_proofs_tree(tmp_path, "p", ["_strategy_s1.lean", "_strategy_s99.lean"])
    prune.prune_problem(conn, tmp_path, "p", dry_run=True)
    pruned_root = tmp_path / "Problems/p/.pruned"
    assert not pruned_root.exists(), (
        "dry_run must not create .pruned/ — that would be a write-side-effect")


def test_prune_problem_warns_on_missing_keep_file(
    conn: sqlite3.Connection, tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When a keep-set file (referenced by winning_chain) is missing from
    disk, prune must warn loudly. Silently skipping means that file's
    `import` edges weren't walked, so downstream dependencies could be
    miscounted as orphan."""
    _seed_problem(conn)
    root = _seed_root(conn)
    win = _seed_strategy(conn, goal_id=root, sid_label="s1")
    sub = _seed_subgoal(conn, problem="p", slug="s1_main_sub_1")
    db.link_subgoal(conn, strategy_id=win, subgoal_id=sub, position=0)
    # Only seed the strategy file + Root.lean, NOT the sub-goal file.
    # winning_chain expects L_s1_main_sub_1.lean per the subgoal row.
    _build_proofs_tree(tmp_path, "p", ["_strategy_s1.lean", "L_orphan.lean"])

    prune.prune_problem(conn, tmp_path, "p", dry_run=True)
    captured = capsys.readouterr()
    assert "missing from disk" in captured.err, (
        f"expected missing-file warning in stderr, got: {captured.err!r}")
    assert "L_s1_main_sub_1.lean" in captured.err


def test_prune_refuses_when_root_not_integrity_verified(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Defense (2026-05-26 post-Jordan): prune must refuse if the root
    has status='proved' but integrity_verified=0 (axiom_probe not yet
    passed). Mechanically-promoted "proved" roots can carry sorry in
    transitive closure; pruning before integrity check could delete
    alternative-chain files needed to bisect the sorryAx.

    The Jordan 2026-05-25 incident saw a chain of mechanically-promoted
    strategies cascade-promote root to 'proved', then auto-prune fire
    before any axiom check, wiping ~235 files. This guard is the
    framework-level counterpart to the `auto-prune removed from
    dispatcher` change.
    """
    _seed_problem(conn)
    _seed_root(conn, verified=False)  # NOT integrity-verified
    _build_proofs_tree(tmp_path, "p", ["_strategy_s99.lean"])

    with pytest.raises(RuntimeError, match="integrity_verified"):
        prune.prune_problem(conn, tmp_path, "p", dry_run=True)


def test_prune_force_bypasses_integrity_gate(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """force=True (CLI: --force) bypasses the integrity_verified gate
    for emergency situations where axiom_probe is known broken."""
    _seed_problem(conn)
    _seed_root(conn, verified=False)
    _build_proofs_tree(tmp_path, "p", ["_strategy_s99.lean"])

    # With force, the gate is skipped and prune runs normally
    removed = prune.prune_problem(conn, tmp_path, "p",
                                  dry_run=True, force=True)
    assert {p.name for p in removed} == {"_strategy_s99.lean"}


def test_dispatcher_does_not_auto_prune() -> None:
    """dispatcher.run must NOT auto-fire prune.prune_problem. Auto-prune
    was removed 2026-05-26 after the jordan_normal_form 2026-05-25 wipe
    incident: two bugs (_IMPORT_RE missed Domain.slug + phantom root path)
    caused prune to delete ~235 of ~252 winning-chain files. Both bugs are
    now fixed (1660200) + tested above, but the blast radius of an
    auto-delete loop firing in production warrants explicit operator
    opt-in. CLI verb `asterism prune <p>` (preferably with `--dry-run`)
    remains the supported path. Reconcile (file/DB drift repair, no
    deletes) stays automatic since it only rewrites file contents.

    Asserts via source inspection rather than a behavioral mock because
    the auto-prune call lived inside dispatcher.run's per-root loop,
    which requires a fully wired daemon to exercise; static check is the
    cheapest tripwire.
    """
    import inspect
    from Tooling.core import dispatcher
    src = inspect.getsource(dispatcher.run)
    assert "prune.prune_problem(" not in src, (
        "dispatcher.run must not call prune.prune_problem; see incident "
        "note in dispatcher.py (the comment block where the call used to "
        "live).")
    # Reconcile must remain automatic.
    assert "prune.reconcile_proved_goals(" in src, (
        "dispatcher.run should still call prune.reconcile_proved_goals "
        "to repair OR-race file/DB drift.")
