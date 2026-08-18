"""Only the top group talks to the human (2026-08-13, user ruling).

`is_deliverable` is a plain "somebody marked it". Two readers want
different subsets of it and the difference is not cosmetic:

  * the TOP group's Mark is a claim addressed to a person — the
    sign-off page, its reject cascade, and what reaches the Library.
  * a SUB-group's Mark is a result handed up to its parent group to
    track. Nobody outside the machine was ever meant to read it.

Measured on union_closed the day this landed: 24 marked goals, 1 from
the top group, 23 inter-group hand-offs. The human was being asked to
vouch for all 24, and the star map faithfully drew 24 diamonds because
it mirrors that page.

THE TRAP THIS FILE EXISTS TO HOLD. `db.deliverables`'s docstring warned
about the sign-off surface and read as an unconditional instruction. It
is not: `librarian/run` uses the same list as HARVEST SEEDS, and the
Ingest gate uses it to ask "did this problem produce anything at all".
Scoping is right for the first, was ruled right for the Library, and is
wrong for the gate. A display bug is annoying; a harvest bug loses
finished work silently.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from Tooling.core import cli
from Tooling.pipeline.librarian import run as librarian_run
from Tooling.quality import review
from Tooling.state import db

ROOT = Path(__file__).resolve().parents[1]


def _mark(conn, gid: int, group_id: "int | None", problem: str) -> None:
    conn.execute(
        "UPDATE goals SET is_deliverable = 1 WHERE id = ?", (gid,))
    ts = "2026-08-13T00:00:00Z"
    conn.execute(
        "INSERT INTO strategist_decisions (problem, triggered_at_tick,"
        " trigger_kind, decision_kind, group_id, target_id, brief,"
        " reason, payload, batch_id, outcome, created_at, updated_at)"
        " VALUES (?, 0, 'routine', 'MarkDeliverable', ?, ?, '', '',"
        "         '{}', NULL, NULL, ?, ?)",
        (problem, group_id, gid, ts, ts))


@pytest.fixture
def tree(conn):
    """A problem with a top group and one sub-group, each having marked
    a deliverable — the union_closed shape in miniature."""
    p = "P"
    now = "2026-08-13T00:00:00Z"
    conn.execute(
        "INSERT INTO problems (name, created_at)"
        " VALUES (?, ?)", (p, now))
    for gid, parent in ((1, None), (2, 1)):
        conn.execute(
            "INSERT INTO groups (id, problem, parent_group_id, status,"
            " created_at, updated_at) VALUES (?, ?, ?, 'active', ?, ?)",
            (gid, p, parent, now, now))
    for gid, slug in ((10, "top_claim"), (11, "sub_part")):
        conn.execute(
            "INSERT INTO goals (id, problem, slug, statement, status, kind,"
            " origin, depth, lean_path, created_at, updated_at)"
            " VALUES (?, ?, ?, 's', 'proved', 'theorem', 'forward', 0, ?,"
            " ?, ?)",
            (gid, p, slug, f"proofs/L_{slug}.lean", now, now))
    _mark(conn, 10, 1, p)      # top group
    _mark(conn, 11, 2, p)      # sub-group
    conn.commit()
    return p


def test_the_top_group_is_findable(tree, conn):
    assert db.top_group_id(conn, tree) == 1


def test_a_problem_older_than_groups_has_no_top_group(conn):
    """None means "no scoping possible", and every caller must then show
    everything — which is what those problems always showed. Silently
    returning an empty list instead would have retro-emptied eleven
    already-ingested problems."""
    assert db.top_group_id(conn, "never-heard-of-it") is None


def test_scoping_keeps_the_claim_and_drops_the_handoff(tree, conn):
    everything = {r["slug"] for r in db.deliverables(conn, problem=tree)}
    assert everything == {"top_claim", "sub_part"}
    scoped = {r["slug"] for r in db.deliverables(
        conn, problem=tree, group_id=db.top_group_id(conn, tree))}
    assert scoped == {"top_claim"}


# ─── which surfaces scope, and which must not ─────────────────────────

def _calls_deliverables_with_group(fn) -> bool:
    """Does this function pass a `group_id=` to `db.deliverables`?"""
    tree_ = ast.parse(inspect.getsource(fn).lstrip())
    for node in ast.walk(tree_):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "deliverables"):
            continue
        if any(k.arg == "group_id" for k in node.keywords):
            return True
    return False


@pytest.mark.parametrize("fn,why", [
    (review.review_data,
     "the sign-off page: a person vouches for the top group's claims"),
    (cli._find_reject_victims,
     "its companion — a person can only reject a claim they were shown"),
])
def test_the_human_surfaces_scope(fn, why):
    assert _calls_deliverables_with_group(fn), (
        f"{fn.__qualname__} must scope to the top group ({why})")


def test_harvest_scopes_because_the_library_is_for_people(tree, conn):
    """User ruling, and it went the way I had argued against: the
    Library is curated FOR people, so what enters it is what the top
    group promoted. A sub-group result the parent never promoted is
    scaffolding.

    Pinned as a live-data assertion rather than by reading the source,
    because what matters is the SEED SET, and the walk below it still
    pulls in whatever those seeds genuinely depend on."""
    seeds = {r["slug"] for r in db.deliverables(
        conn, problem=tree, group_id=db.top_group_id(conn, tree))}
    assert seeds == {"top_claim"}
    src = inspect.getsource(librarian_run)
    assert "group_id=db.top_group_id" in src, (
        "harvest seeds must scope to the top group")


def test_the_ingest_gate_does_not_scope():
    """The one that must NOT move. It asks "did this problem produce
    anything at all" — a question about the machine's work, not the
    human's reading list. Scoping it would refuse Ingest to a problem
    whose sub-groups did all the finished work, which is a different
    decision from what was ruled here and has not been made."""
    from Tooling.pipeline import strategist
    src = inspect.getsource(strategist)
    marker = "if not db.deliverables(conn, problem=problem) and not root_proved"
    assert marker in src, (
        "the Ingest existence check must stay unscoped — see this test's "
        "docstring before 'fixing' it")


# ─── what the map is given ────────────────────────────────────────────

def test_the_map_is_told_who_marked_it_rather_than_being_filtered(tree, conn):
    """The star map must be able to DISTINGUISH, not made to HIDE. It
    draws every marked goal; `human_facing_claim` is what lets it draw
    the two kinds differently."""
    from Tooling.serve import data as sdata
    detail = sdata.problem_detail(conn, ROOT, tree)
    by_slug = {g["slug"]: g for g in detail["goals"]}
    assert by_slug["top_claim"]["is_deliverable"] is True
    assert by_slug["top_claim"]["human_facing_claim"] is True
    assert by_slug["top_claim"]["marked_by_group"] == 1
    # still present, still a deliverable — just not a claim for a person
    assert by_slug["sub_part"]["is_deliverable"] is True
    assert by_slug["sub_part"]["human_facing_claim"] is False
    assert by_slug["sub_part"]["marked_by_group"] == 2
