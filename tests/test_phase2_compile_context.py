"""Phase 2 — compile_context Strategist directive + brief sections.

Covers Step 5 acceptance: `compile_context` accepts `decision_id`
parameter, renders `## Strategist directive` when problems.
strategist_directive is non-empty, renders `## The argument for this brick` when
decision_id points to a Strategist Inject decision row.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from Tooling.agent.context import compile_context
from Tooling.state import db, intent as intent_mod


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a tmp workspace with Problems/p/proofs/."""
    monkeypatch.chdir(tmp_path)
    pdir = tmp_path / "Problems" / "p"
    pdir.mkdir(parents=True)
    (pdir / "proofs").mkdir()
    (pdir / "Root.lean").write_text(
        "theorem main : T := by sorry\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def conn(workspace: Path) -> sqlite3.Connection:
    c = db.connect()
    db.init_schema(c)
    c.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done)"
        " VALUES ('p', ?, 1)",
        (db.now(),),
    )
    c.commit()
    return c


def _insert_root(conn: sqlite3.Connection) -> int:
    return db.insert_goal(
        conn, problem="p", slug="main",
        lean_path="Problems/p/Root.lean", statement="T",
        origin="root", depth=0,
    )


def _make_attempts_dir(workspace: Path) -> Path:
    """Set up `.attempts/<pid>/` to satisfy compile_context's path
    walking (.attempts/<pid> -> .attempts -> workspace)."""
    pid = "test-pid"
    attempts_dir = workspace / ".attempts" / pid
    attempts_dir.mkdir(parents=True, exist_ok=True)
    return attempts_dir


def _read_context(attempts_dir: Path) -> str:
    return (attempts_dir / "Context.md").read_text(encoding="utf-8")


def _fake_intent() -> intent_mod.ProblemIntent:
    return intent_mod.ProblemIntent(problem="p", charter="T")


# ---------------------------------------------------------------------
# Directive section
# ---------------------------------------------------------------------

def test_no_directive_no_section(workspace: Path,
                                 conn: sqlite3.Connection) -> None:
    """Default (no directive set) → no `## Strategist directive` section."""
    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, intent=_fake_intent(),
        attempts_dir=attempts_dir, kind="backward",
    )
    text = _read_context(attempts_dir)
    assert "## Strategist directive" not in text


def test_directive_rendered_when_set(workspace: Path,
                                     conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE problems SET strategist_directive = ? WHERE name = 'p'",
        ("Library now has contour_deformation_piecewise; prefer it.",),
    )
    conn.commit()

    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, intent=_fake_intent(),
        attempts_dir=attempts_dir, kind="backward",
    )
    text = _read_context(attempts_dir)
    assert "## Strategist directive" in text
    assert "contour_deformation_piecewise" in text


def test_empty_directive_not_rendered(workspace: Path,
                                      conn: sqlite3.Connection) -> None:
    """Whitespace-only directive treated as absent."""
    conn.execute(
        "UPDATE problems SET strategist_directive = ? WHERE name = 'p'",
        ("   \n   ",),
    )
    conn.commit()

    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, intent=_fake_intent(),
        attempts_dir=attempts_dir, kind="backward",
    )
    text = _read_context(attempts_dir)
    assert "## Strategist directive" not in text


# ---------------------------------------------------------------------
# Brief section
# ---------------------------------------------------------------------

def _insert_decision(conn: sqlite3.Connection, *, kind: str,
                     brief: str | None = None,
                     reason: str | None = None) -> int:
    ts = db.now()
    cur = conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, brief, reason, payload,"
        " created_at, updated_at)"
        " VALUES ('p', 1, 'routine', ?, ?, ?, '{}', ?, ?)",
        (kind, brief, reason, ts, ts),
    )
    conn.commit()
    return int(cur.lastrowid)


def test_no_decision_id_no_brief_section(workspace: Path,
                                         conn: sqlite3.Connection) -> None:
    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, intent=_fake_intent(),
        attempts_dir=attempts_dir, kind="backward",
        decision_id=None,
    )
    text = _read_context(attempts_dir)
    assert "## The argument for this brick" not in text


def test_brief_rendered_when_decision_id_set(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    did = _insert_decision(
        conn, kind="Inject",
        brief="## Need\nLemma X for contour deformation",
    )
    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, intent=_fake_intent(),
        attempts_dir=attempts_dir, kind="backward",
        decision_id=did,
    )
    text = _read_context(attempts_dir)
    assert "## The argument for this brick" in text
    assert "contour deformation" in text


def test_brief_skipped_when_brief_column_null(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """ConfirmShelve decision (no brief, only reason) → brief section
    not rendered."""
    did = _insert_decision(conn, kind="ConfirmShelve",
                           reason="truly dead")
    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, intent=_fake_intent(),
        attempts_dir=attempts_dir, kind="backward",
        decision_id=did,
    )
    text = _read_context(attempts_dir)
    assert "## The argument for this brick" not in text


def test_both_directive_and_brief_render(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Directive + Inject brief both present → both sections appear,
    directive first (problem-level standing)."""
    conn.execute(
        "UPDATE problems SET strategist_directive = ? WHERE name = 'p'",
        ("Prefer L_alpha over manual case-split.",),
    )
    conn.commit()
    did = _insert_decision(
        conn, kind="Inject",
        brief="## Need\nFollow up on L_alpha",
    )
    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, intent=_fake_intent(),
        attempts_dir=attempts_dir, kind="backward",
        decision_id=did,
    )
    text = _read_context(attempts_dir)
    assert "## Strategist directive" in text
    assert "## The argument for this brick" in text
    # Ordering: directive before brief
    assert text.index("## Strategist directive") < text.index("## The argument for this brick")


def test_brief_decision_id_nonexistent(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """decision_id pointing to no-such-row → no brief, no crash."""
    gid = _insert_root(conn)
    goal = db.get_goal(conn, gid)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(
        conn, goal=goal, intent=_fake_intent(),
        attempts_dir=attempts_dir, kind="backward",
        decision_id=99999,
    )
    text = _read_context(attempts_dir)
    assert "## The argument for this brick" not in text


# ------------------------------------------------- the brick's argument
# (2026-08-11) The Inject's prose became the part of its batch's
# `## Proof` that settles the brick. Two consequences the framework has
# to get right: the passage has to reach work the author never saw (the
# sub-goals a worker invents), and the whole `## Proof` has to stop
# riding along once something more specific answered.

def _decision_for_goal(conn: sqlite3.Connection, gid: int, proof: str) -> int:
    did = _insert_decision(conn, kind="Inject", brief=proof)
    conn.execute("UPDATE strategist_decisions SET produced_goal_id = ?"
                 " WHERE id = ?", (str(gid), did))
    conn.commit()
    return did


def _subgoal_of(conn: sqlite3.Connection, parent: int, slug: str) -> int:
    sid = int(conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, status, created_by,"
        " created_at) VALUES (?, ?, 'proposed', 'backward', ?)",
        (parent, f"Problems/p/proofs/_strategy_{slug}.lean",
         db.now())).lastrowid)
    gid = db.insert_goal(conn, problem="p", slug=slug,
                         lean_path=f"Problems/p/proofs/L_{slug}.lean",
                         statement="T", origin="backward")
    conn.execute("INSERT INTO strategy_subgoals (strategy_id, subgoal_id,"
                 " position) VALUES (?, ?, 0)", (sid, gid))
    conn.commit()
    return gid


def test_an_invented_subgoal_inherits_its_ancestors_argument(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """About half of all worker spawns are sub-goals a worker created,
    with no decision of their own. They are working INSIDE the passage
    their parent was dispatched under — a `## Proof` may carry no gaps,
    so a decomposition only outsources part of one — and the walk goes
    up through `strategies`, so it lands on the nearest injected
    ancestor rather than the newest thing in the tree."""
    parent = _insert_root(conn)
    _decision_for_goal(conn, parent, "## Need\nthe fibre split, in full")
    kid = _subgoal_of(conn, parent, "kid")
    grandkid = _subgoal_of(conn, kid, "grandkid")

    attempts_dir = _make_attempts_dir(workspace)
    compile_context(conn, goal=db.get_goal(conn, grandkid),
                    intent=_fake_intent(), attempts_dir=attempts_dir,
                    kind="backward", decision_id=None)
    text = _read_context(attempts_dir)
    assert "## The argument for this brick" in text
    assert "the fibre split, in full" in text


def test_sibling_strategies_never_see_each_others_argument(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """Two live strategies on one OR node are two attempts at the same
    goal, dispatched under different arguments. The walk climbs through
    `strategy_subgoals`, so each subtree reaches its own."""
    a = _insert_root(conn)
    _decision_for_goal(conn, a, "ROUTE A: via the weight function")
    b = db.insert_goal(conn, problem="p", slug="other",
                       lean_path="Problems/p/proofs/L_other.lean",
                       statement="T", origin="forward")
    _decision_for_goal(conn, b, "ROUTE B: via the lattice")
    kid_a = _subgoal_of(conn, a, "kid_a")

    attempts_dir = _make_attempts_dir(workspace)
    compile_context(conn, goal=db.get_goal(conn, kid_a),
                    intent=_fake_intent(), attempts_dir=attempts_dir,
                    kind="backward", decision_id=None)
    text = _read_context(attempts_dir)
    assert "ROUTE A" in text
    assert "ROUTE B" not in text


def test_a_cited_siblings_subtree_never_inherits_the_citing_brief(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """v44 — the incident shape (2026-08-25): a redispatch Backward on
    goal A cites the pre-existing sibling B as a wait edge; A's brief
    literally says 'work goal A'. The walk crossing that cited edge
    handed B's whole subtree A's brief, and every dispatch there died
    at intake as mis-aimed (six declines in three minutes). Cited edges
    must not conduct — B's subtree keeps its own line's argument."""
    # B's real line: root r (authorised) → minted B → minted kid_b.
    # B itself has no decision — the incident's shape exactly.
    r = _insert_root(conn)
    _decision_for_goal(conn, r, "B'S PARENT LINE: the census argument")
    b = _subgoal_of(conn, r, "b")
    kid_b = _subgoal_of(conn, b, "kid_b")
    # A: a NEWER authorised goal whose redispatch strategy cites B.
    # Both briefs sit at the same walk depth from kid_b; the tie-break
    # (d.id DESC) picks A's — unless the cited edge is pruned.
    a = db.insert_goal(conn, problem="p", slug="a",
                       lean_path="Problems/p/proofs/L_a.lean",
                       statement="T", origin="backward")
    _decision_for_goal(conn, a, "WORK GOAL A ONLY: the codec identities")
    sid_a = int(conn.execute(
        "INSERT INTO strategies (goal_id, lean_path, status, created_by,"
        " created_at) VALUES (?, 'Problems/p/proofs/_strategy_cite.lean',"
        " 'proposed', 'backward', ?)", (a, db.now())).lastrowid)
    db.link_subgoal(conn, strategy_id=sid_a, subgoal_id=b, position=0,
                    link_kind="cited")

    attempts_dir = _make_attempts_dir(workspace)
    compile_context(conn, goal=db.get_goal(conn, kid_b),
                    intent=_fake_intent(), attempts_dir=attempts_dir,
                    kind="backward", decision_id=None)
    text = _read_context(attempts_dir)
    assert "B'S PARENT LINE" in text
    assert "WORK GOAL A ONLY" not in text


def _pass_programme(conn: sqlite3.Connection, proof: str) -> None:
    from Tooling.state import programme
    programme.record_pass(
        conn, "p",
        f"# T\n## Argument\na\n## Proof\n{proof}\n## Roadmap\nr\n",
        verdict={}, dialogue=[], rounds=0, batch_id=None, group_id=None)
    conn.commit()


def test_the_whole_proof_rides_only_when_nothing_answered(
    workspace: Path, conn: sqlite3.Connection,
) -> None:
    """The fallback IS the old behaviour, which is what makes this
    landable on a live tree: every goal in flight predates the field, so
    every one of them keeps getting the whole `## Proof` until a batch
    fills theirs in. With a passage in hand, the rest of the batch is
    other bricks' business and rides the pointer."""
    _pass_programme(conn, "SECTION ONE. SECTION TWO. SECTION THREE.")
    gid = _insert_root(conn)
    attempts_dir = _make_attempts_dir(workspace)

    compile_context(conn, goal=db.get_goal(conn, gid),
                    intent=_fake_intent(), attempts_dir=attempts_dir,
                    kind="backward", decision_id=None)
    text = _read_context(attempts_dir)
    assert "SECTION TWO" in text                       # no passage → all of it

    did = _decision_for_goal(conn, gid, "just my part")
    attempts_dir = _make_attempts_dir(workspace)
    compile_context(conn, goal=db.get_goal(conn, gid),
                    intent=_fake_intent(), attempts_dir=attempts_dir,
                    kind="backward", decision_id=did)
    text = _read_context(attempts_dir)
    assert "just my part" in text
    assert "SECTION TWO" not in text
    assert "Full Programme" in text                    # …but reachable
