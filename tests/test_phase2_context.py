"""Phase 2 — Strategist Context.md compilation.

Covers `phase2_context.compile_strategist_context` review_context
surfacing (Phase 2 §2.2 spec). The take-5 SG regression came from the
pending_review section missing three signals the spec required:
failure reason summary, existing strategy content, and ancestor chain.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.agent import phase2_context
from Tooling.state import db, manifest


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "Manifest.md").write_text(
        "---\nproblem: p\n---\n\n## Statement\nT\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def mfst() -> manifest.Manifest:
    return manifest.Manifest(problem="p", statement="T")


def _insert_problem(conn: sqlite3.Connection, name: str = "p") -> None:
    conn.execute(
        "INSERT INTO problems (name, manifest_path, created_at)"
        " VALUES (?, '', ?)", (name, db.now()),
    )
    conn.commit()


def _insert_root(conn: sqlite3.Connection, slug: str = "main") -> int:
    return db.insert_goal(
        conn, problem="p", slug=slug, lean_path=f"P/{slug}.lean",
        statement="T", origin="root", depth=0, entry_kind="Backward",
    )


def _insert_strategy(conn: sqlite3.Connection, goal_id: int,
                     proposal_md: str = "",
                     status: str = "proposed") -> int:
    cur = conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, scratch_path, status,"
        " proposal_md, created_by, created_at)"
        " VALUES (?, '', '', ?, ?, 'test', ?)",
        (goal_id, status, proposal_md, db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


def _link_subgoal(conn: sqlite3.Connection, *, strategy_id: int,
                  subgoal_id: int, position: int = 0) -> None:
    conn.execute(
        "INSERT INTO strategy_subgoals (strategy_id, subgoal_id, position)"
        " VALUES (?, ?, ?)", (strategy_id, subgoal_id, position),
    )
    conn.commit()


def _insert_dead_attempt(conn: sqlite3.Connection, *, target_id: int,
                         failure_reason: str, proposal_md: str,
                         failure_detail: str = "",
                         target_kind: str = "Goal",
                         pipeline_id: str = "pid-x") -> int:
    # dead_attempts.pipeline_id FK -> pipelines.id; seed a row first.
    conn.execute(
        "INSERT OR IGNORE INTO pipelines (id, kind, target_id, target_kind,"
        " status, outcome, started_at, finished_at)"
        " VALUES (?, 'Backward', ?, ?, 'failed', 'failed', ?, ?)",
        (pipeline_id, str(target_id), target_kind, db.now(), db.now()),
    )
    cur = conn.execute(
        "INSERT INTO dead_attempts (target_id, target_kind, pipeline_id,"
        " failure_reason, failure_detail, proposal_md, artifacts, ts)"
        " VALUES (?, ?, ?, ?, ?, ?, '', ?)",
        (str(target_id), target_kind, pipeline_id, failure_reason,
         failure_detail, proposal_md, db.now()),
    )
    conn.commit()
    return int(cur.lastrowid)


# ---------------------------------------------------------------------
# Pending-review enrichment — the take-5 SG bug surface
# ---------------------------------------------------------------------

def test_pending_review_surfaces_backward_shelve_proposal(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """Regression — SG take 5: Backward agent declined with a detailed
    shelve brief (5 missing Forward lemmas listed in dead_attempts.
    proposal_md). Pre-fix Context.md hid this from Strategist, which
    then Reopen'd with a redundant directive that asked for exactly the
    missing lemmas as if they existed. After fix, the agent's brief
    appears verbatim under '### Recent failed attempts'."""
    _insert_problem(conn)
    root = _insert_root(conn)
    backward_brief = (
        "-- decline: shelve\n"
        "-- ## Missing scaffolding for Kelly's proof\n"
        "-- Needed Forward lemmas:\n"
        "-- 1. lineThrough\n"
        "-- 2. perpFoot\n"
        "-- 3. perpDistSq\n"
    )
    _insert_dead_attempt(
        conn, target_id=root, failure_reason="agent_shelved",
        failure_detail="backward declined: shelve",
        proposal_md=backward_brief,
    )

    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="pending_review",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=root,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Recent failed attempts on this goal" in text
    assert "agent_shelved" in text
    assert "Needed Forward lemmas" in text
    assert "lineThrough" in text
    assert "perpFoot" in text


def test_pending_review_surfaces_existing_strategy_content(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """Spec §2.2 review_context: '既有 strategy 內容'. Strategist needs
    to know what decomposition was tried before deciding Reopen with
    directive vs Inject Forward."""
    _insert_problem(conn)
    root = _insert_root(conn)
    sid = _insert_strategy(
        conn, root,
        proposal_md="Tried Kelly minimiser split; sub_a, sub_b.",
        status="dead",
    )
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="pending_review",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=root,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Existing strategies on this goal" in text
    assert f"s{sid}" in text
    assert "Kelly minimiser split" in text
    assert "status=`dead`" in text


def test_pending_review_walks_ancestor_chain_to_root(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """Spec §2.2 review_context: 'ancestor 鏈'. Walk subgoal → parent
    strategy → strategy.goal_id upward until origin='root'."""
    _insert_problem(conn)
    root = _insert_root(conn, slug="main")
    s_root = _insert_strategy(conn, root, status="proposed")
    mid = db.insert_goal(
        conn, problem="p", slug="mid", lean_path="P/mid.lean",
        statement="MidStmt", origin="backward", depth=1,
    )
    _link_subgoal(conn, strategy_id=s_root, subgoal_id=mid)
    s_mid = _insert_strategy(conn, mid, status="proposed")
    leaf = db.insert_goal(
        conn, problem="p", slug="leaf", lean_path="P/leaf.lean",
        statement="LeafStmt", origin="backward", depth=2,
    )
    _link_subgoal(conn, strategy_id=s_mid, subgoal_id=leaf)

    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="pending_review",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=leaf,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Ancestor chain" in text
    assert "`mid`" in text
    assert "`main`" in text
    assert "(ROOT)" in text


def test_root_pending_review_marks_self_root_chain(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """A root goal pending-reviewed has no upward chain. Section emits a
    'self is root' note so Strategist sees the placeholder rather than
    missing the section entirely."""
    _insert_problem(conn)
    root = _insert_root(conn)
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="pending_review",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=root,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Ancestor chain" in text
    assert "self" in text or "root" in text


# ---------------------------------------------------------------------
# Other triggers leave new sections out
# ---------------------------------------------------------------------

def test_routine_trigger_omits_review_sections(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """T1 routine trigger: review-specific sections (failure brief,
    existing strategies, ancestor chain) must not appear — they target
    one goal and would be noise outside T2."""
    _insert_problem(conn)
    root = _insert_root(conn)
    _insert_dead_attempt(
        conn, target_id=root, failure_reason="agent_shelved",
        proposal_md="should not appear in routine context",
    )
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="routine",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=None,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Recent failed attempts on this goal" not in text
    assert "### Existing strategies on this goal" not in text
    assert "### Ancestor chain" not in text
    assert "should not appear in routine context" not in text


def test_first_launch_trigger_omits_review_sections(
    workspace: Path, conn: sqlite3.Connection,
    mfst: manifest.Manifest, tmp_path: Path,
) -> None:
    """T0 first_launch: bootstrap context, no review target."""
    _insert_problem(conn)
    _insert_root(conn)
    attempts_dir = tmp_path / "_attempts_strategist"
    attempts_dir.mkdir()
    out = phase2_context.compile_strategist_context(
        conn, problem="p", trigger_kind="first_launch",
        attempts_dir=attempts_dir, workspace=workspace, mfst=mfst,
        pending_review_id=None,
    )
    text = out.read_text(encoding="utf-8")
    assert "### Recent failed attempts on this goal" not in text
    assert "### Existing strategies on this goal" not in text
    assert "### Ancestor chain" not in text
