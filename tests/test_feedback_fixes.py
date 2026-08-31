"""Fixes for the 08-31 feedback triage (owner order: fix 1/2/3/4).

Two Sonnet triage passes over docs/internal/agent_feedback.md (local
union_closed run + the flagship Erdos fleet) found four VERIFIED-REAL
high-frequency issues:

1. `inspect({decl:...})` ignored the caller's problem — a common slug
   (`main`) answered with a pile of unrelated problems' goals (100
   reports in one day, 33% of the local file).
2. Context.md's `## Programme` section embedded the Programme body
   verbatim; its `# <Title>` (H1) closed the H2 section immediately,
   so section-reads saw an EMPTY Programme and the Argument/Roadmap
   floated as top-level strangers (13 reports, the strategist's
   primary audit read).
3. TREE.md is written by the dispatcher on its own clock, so a wake's
   Context and its TREE.md could describe two different moments (131
   reports on the fleet — the #1 theme). The wake now refreshes
   TREE.md from the same connection its sections read.
4. The `.lake/packages/...` teaching example is workspace-rooted, but
   a spawn's cwd is its problem dir — the literal example silently
   found nothing (37 reports). `.lake/...` specs now resolve against
   the workspace root.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.knowledge import workspace_query as wq
from Tooling.state import db, groups


def _ws(tmp_path: Path) -> Path:
    (tmp_path / "Problems" / "Cat" / "a" / "proofs").mkdir(parents=True)
    (tmp_path / "Problems" / "Cat" / "b" / "proofs").mkdir(parents=True)
    (tmp_path / "Tooling").mkdir()   # workspace_of marker
    c = db.connect(tmp_path / "asterism.db")
    db.init_schema(c)
    for name in ("Cat.a", "Cat.b"):
        c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
                  " VALUES (?, ?, 1)", (name, db.now()))
    db.insert_goal(c, problem="Cat.a", slug="main",
                   lean_path="Problems/Cat/a/proofs/L_main.lean",
                   statement="STMT_A_ONLY", origin="root", depth=0)
    db.insert_goal(c, problem="Cat.b", slug="main",
                   lean_path="Problems/Cat/b/proofs/L_main.lean",
                   statement="STMT_B_ONLY", origin="root", depth=0)
    db.insert_goal(c, problem="Cat.b", slug="only_b",
                   lean_path="Problems/Cat/b/proofs/L_only_b.lean",
                   statement="ONLY_B_STMT", origin="forward", depth=1)
    c.commit(); c.close()
    return tmp_path


def test_decl_answers_from_the_callers_problem_first(tmp_path):
    _ws(tmp_path)
    out = wq.run_queries([{"decl": "main"}],
                         cwd=tmp_path / "Problems" / "Cat" / "a",
                         per_query_chars=4000)
    assert "STMT_A_ONLY" in out, out
    assert "STMT_B_ONLY" not in out, \
        "a common slug must not drown the caller in other problems' goals"


def test_decl_falls_back_across_problems_when_nothing_local(tmp_path):
    _ws(tmp_path)
    out = wq.run_queries([{"decl": "only_b"}],
                         cwd=tmp_path / "Problems" / "Cat" / "a",
                         per_query_chars=4000)
    assert "ONLY_B_STMT" in out, "cross-problem lookup still works"


def test_programme_body_headings_are_demoted_in_context(tmp_path, monkeypatch):
    from Tooling.agent.phase2_context import compile as C
    monkeypatch.chdir(tmp_path)
    c = db.connect(tmp_path / "asterism.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p', ?, 1)", (db.now(),))
    c.execute(
        "INSERT INTO programme_revisions (problem, rev, body, status,"
        " dialogue, rounds, created_at)"
        " VALUES ('p', 1, ?, 'passed', '[]', 1, ?)",
        ("# Grand title\n\n## Argument\n\nwhy this batch\n\n"
         "## Proof\n\nProof body\n\n## Roadmap\n\nNOW\n", db.now()))
    c.commit()
    attempts = tmp_path / "_a"; attempts.mkdir()
    lines = C._section_programme_strategist(c, "p", None,
                                            attempts_dir=attempts)
    text = "\n".join(lines)
    i = text.index("## Programme (rev 1")
    body = text[i + 1:]
    for ln in body.splitlines()[1:]:
        assert not ln.startswith("# ") and not ln.startswith("## "), \
            f"embedded heading closes the section early: {ln!r}"
    assert "why this batch" in text and "Argument" in text


def test_lake_paths_resolve_against_the_workspace_root(tmp_path):
    _ws(tmp_path)
    lib = tmp_path / ".lake" / "packages" / "mathlib" / "Mathlib"
    lib.mkdir(parents=True)
    (lib / "Foo.lean").write_text("theorem THE_LEMMA : True := trivial\n",
                                  encoding="utf-8")
    out = wq.run_queries(
        [{"grep": "THE_LEMMA", "in": ".lake/packages/mathlib/Mathlib"}],
        cwd=tmp_path / "Problems" / "Cat" / "a", per_query_chars=2000)
    assert "THE_LEMMA" in out, out


def test_judge_projection_gets_a_fresh_tree(tmp_path, monkeypatch):
    from Tooling.pipeline import adversary
    monkeypatch.chdir(tmp_path)
    c = db.connect(tmp_path / "asterism.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p', ?, 1)", (db.now(),))
    groups.ensure_top_group(c, "p")
    db.insert_goal(c, problem="p", slug="fresh_goal_xyz",
                   lean_path="Problems/p/proofs/L_x.lean",
                   statement="True", origin="root", depth=0)
    c.commit()
    pdir = tmp_path / "Problems" / "p"; (pdir / "proofs").mkdir(parents=True)
    (pdir / "TREE.md").write_text("OLD_TREE_SNAPSHOT\n", encoding="utf-8")
    attempts = tmp_path / "_a"; attempts.mkdir()
    proj = adversary.build_projection(
        round_no=1, attempts_dir=attempts, problem_dir=pdir, conn=c,
        problem="p", proposal_body="# T\n\n## Argument\n\nx\n",
        decisions=[], dialogue=[], proof_warn=None)
    tree = (proj / "TREE.md").read_text(encoding="utf-8")
    assert "fresh_goal_xyz" in tree and "OLD_TREE_SNAPSHOT" not in tree, \
        "the judge must see the tree as of THIS round, not the dispatcher's last render"


def test_strategist_wake_refreshes_tree_on_disk(tmp_path):
    from Tooling.agent.phase2_context.compile import _section_tree_inline
    c = db.connect(tmp_path / "asterism.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at, bootstrap_done)"
              " VALUES ('p', ?, 1)", (db.now(),))
    db.insert_goal(c, problem="p", slug="fresh_goal_xyz",
                   lean_path="Problems/p/proofs/L_x.lean",
                   statement="True", origin="root", depth=0)
    c.commit()
    pdir = tmp_path / "Problems" / "p"; pdir.mkdir(parents=True)
    (pdir / "TREE.md").write_text("OLD_TREE_SNAPSHOT\n", encoding="utf-8")
    _section_tree_inline(c, tmp_path, "p")
    tree = (pdir / "TREE.md").read_text(encoding="utf-8")
    assert "fresh_goal_xyz" in tree and "OLD_TREE_SNAPSHOT" not in tree, \
        "the section points at TREE.md — the pointer must not point at another moment"
