"""`validate_file`'s parity verdict — does this green mean what a green
usually means? (#183)

The sandbox and the real build assemble DIFFERENT objects on purpose: the
probe inlines a sibling's stub so it can elaborate without that sibling
being built, while commit gives the sibling its own module and an import
line. Comparing the two units wholesale would alarm on every call. What
must agree is narrower — every name the probe resolved through an inlined
stub has to be a name the build can resolve too.

#179 hid for a week because the disagreement reached the AGENT as
`Unknown identifier`, which reads as "that sibling does not exist". 37
reports, several saying plainly they could not tell that from "wrong
approach". The cost was not the rebuild; it was the abandoned line of
attack.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.lsp import gateway as gw


@pytest.fixture
def ws(tmp_path: Path, conn) -> Path:
    (tmp_path / "Problems" / "T" / "p" / "proofs").mkdir(parents=True)
    return tmp_path


def _seed(ws: Path, rows: "list[tuple[str, str]]") -> None:
    """rows = [(slug, status)] in a real on-disk DB (the helper opens the
    workspace's own file, which is how the gateway reaches it)."""
    from Tooling.state import db
    c = db.connect(ws / "asterism.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at)"
              " VALUES ('T.p', '2026-08-10')")
    for slug, status in rows:
        c.execute(
            "INSERT INTO goals (problem, slug, lean_path, statement, status,"
            " origin, created_at, updated_at) VALUES ('T.p', ?, ?, 'X', ?,"
            " 'backward', '2026-08-10', '2026-08-10')",
            (slug, f"Problems/T.p/proofs/L_{slug}.lean", status))
    c.commit()
    c.close()


def test_no_siblings_is_exact(ws: Path) -> None:
    out = gw._parity_for("theorem t : True := trivial", "T.p", ws, [],
                         {"imports": []})
    assert out["state"] == "exact"


def test_a_proved_sibling_is_exact(ws: Path) -> None:
    """The probe saw the same declarations lake will."""
    _seed(ws, [("helper", "proved")])
    out = gw._parity_for("x", "T.p", ws, ["helper"], {"imports": []})
    assert out["state"] == "exact"
    assert out["proved_siblings"] == ["helper"]


def test_an_unproved_sibling_makes_the_green_conditional(ws: Path) -> None:
    """The irreducible case: the probe elaborated against `:= by sorry`
    and the real build will use whatever that goal becomes. Legitimate,
    common — and it must NOT render as the same green, or a downstream
    reader treats a conditional result as settled."""
    _seed(ws, [("in_flight", "attempting")])
    out = gw._parity_for("x", "T.p", ws, ["in_flight"], {"imports": []})
    assert out["state"] == "conditional"
    assert out["depends_on"] == ["in_flight"]
    assert "conditional on them proving as declared" in out["note"]


def test_an_unknown_sibling_is_named_as_a_FRAMEWORK_error(ws: Path) -> None:
    """Neither a goal nor covered by a commit import: the probe answered
    a question the build was never going to be asked. The message says
    whose error it is, because the whole cost of #179 was the agent
    reading it as its own."""
    _seed(ws, [])
    out = gw._parity_for("x", "T.p", ws, ["ghost"], {"imports": []})
    assert out["state"] == "unresolved"
    assert out["framework_parity_error"] == ["ghost"]
    assert "not your error" in out["note"]


def test_a_commit_import_covers_a_sibling_with_no_goal_row(ws: Path) -> None:
    """A batch stub has no goal row yet but commit will import it — that
    is covered, not a defect."""
    _seed(ws, [])
    out = gw._parity_for(
        "x", "T.p", ws, ["batch_mate"],
        {"imports": ["import Problems.T.p.proofs.L_batch_mate"]})
    assert out["state"] == "exact"


def test_parity_never_breaks_validate(tmp_path: Path) -> None:
    """No DB on disk at all — validate must still answer. A guard that
    can fail the thing it guards is worse than no guard."""
    out = gw._parity_for("x", "T.p", tmp_path, ["whatever"], {"imports": []})
    assert out["state"] in ("exact", "conditional", "unresolved")


def test_import_match_is_exact_module_identity_never_substring(
        ws: Path) -> None:
    """`"L_foo" in imports` (a joined string) matched `L_foobar`'s
    import and marked an unproved sibling proved (feedback 2026-08-25,
    soundness-adjacent missignal). Exact name or dotted suffix only."""
    header = {"imports": ["Problems.T.p.proofs.L_foobar"]}
    out = gw._parity_for("x", "T.p", ws, ["foo"], header)
    assert out["state"] == "unresolved", \
        "a substring of another module's name is not a covering import"
    out2 = gw._parity_for("x", "T.p", ws, ["foobar"], header)
    assert out2["state"] == "exact" and out2["proved_siblings"] == ["foobar"]


def test_parity_mirrors_commits_ancestor_cycle_predicate(ws: Path) -> None:
    """Feedback x2: validate said "citation ok", commit rejected the
    circularity. With the session's goal_id threaded in, the SAME
    `db.strict_ancestor_ids` walk runs here and names the cycle before
    the agent builds on it."""
    from Tooling.state import db
    c = db.connect(ws / "asterism.db")
    db.init_schema(c)
    c.execute("INSERT INTO problems (name, created_at)"
              " VALUES ('T.p', 't')")
    root = db.insert_goal(c, problem="T.p", slug="root",
                          lean_path="P/root.lean", statement="R",
                          origin="root", depth=0)
    kid = db.insert_goal(c, problem="T.p", slug="kid",
                         lean_path="P/kid.lean", statement="K",
                         origin="backward", depth=1)
    sid = db.insert_strategy(c, goal_id=root, proposal_md="s",
                         lean_path="P/s.lean", created_by="test")
    db.link_subgoal(c, strategy_id=sid, subgoal_id=kid, position=0)
    c.commit(); c.close()
    out = gw._parity_for("x", "T.p", ws, ["root"], {"imports": []},
                         goal_id=kid)
    assert out.get("ancestor_cycle") == ["root"]
    assert "circular" in out["ancestor_cycle_note"]
    # no goal identity (old client) -> no cycle check, never an error
    out2 = gw._parity_for("x", "T.p", ws, ["root"], {"imports": []})
    assert "ancestor_cycle" not in out2
