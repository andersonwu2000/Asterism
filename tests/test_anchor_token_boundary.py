"""An anchor that lands inside a name is refused, not honoured.

`apply_edit`'s charter is that the text either is there, exactly once,
or it is not — "a stale mental model becomes a refusal". For one class
it did not: the anchor bound as a substring of a longer name, the tool
edited a span the agent had never described, and it REPORTED SUCCESS.

The live shape, four times on 08-12/13/14: `end Problems` resolving
against `end Problems.Combinatorics.union_closed`. The span stopped 13
characters early and `.Combinatorics.union_closed` was left dangling in
the file under a clean verdict.

WHY NOT `\\w`. The boundary character in that incident is a DOT. An
ASCII word boundary lets it through and the bug outlives its own fix,
so the test is "does this character continue a Lean name" — which
includes `.`, `_`, `'`, subscripts and Greek.

One chokepoint covers all three anchor forms: since `b95082eb` the
closing anchor of `replace_between` resolves through `_find_unique` too
(the regional variant with `start=`).
"""
from __future__ import annotations

import pytest

from Tooling.lsp import edits

FILE = ("import Mathlib\n"
        "namespace Problems.Combinatorics.union_closed\n"
        "\n"
        "theorem uc_head : True := trivial\n"
        "\n"
        "end Problems.Combinatorics.union_closed\n")


@pytest.mark.parametrize("anchor,collides_with", [
    # the two shapes agents actually filed, both single-hit
    ("namespace Problems", "namespace Problems.Combinatorics.union_closed"),
    ("end Problems", "end Problems.Combinatorics.union_closed"),
    ("theorem uc_", "theorem uc_head"),
])
def test_an_anchor_inside_a_name_is_refused(anchor: str, collides_with: str):
    with pytest.raises(edits.EditError) as e:
        edits._find_unique(FILE, anchor, 0, "anchor")
    msg = str(e.value)
    assert "matches inside" in msg, msg
    # The refusal quotes what it collided with: a refusal that says only
    # "no" costs the same round trip as a wrong edit and teaches less.
    assert collides_with in msg, msg


def test_an_ambiguous_anchor_keeps_its_own_refusal():
    """`union_closed` appears twice here, so the older ambiguity branch
    answers first — and should. The boundary guard adds a refusal, it
    does not take one over."""
    with pytest.raises(edits.EditError) as e:
        edits._find_unique(FILE, "union_closed", 0, "anchor")
    assert "appears" in str(e.value) and "unique" in str(e.value)


@pytest.mark.parametrize("anchor", [
    "theorem uc_head",             # a whole name
    "import Mathlib",              # no identifier on either edge
    "namespace Problems.Combinatorics.union_closed",   # the full line
    ":= trivial",                  # starts on punctuation
])
def test_a_well_formed_anchor_still_resolves(anchor: str):
    assert edits._find_unique(FILE, anchor, 0, "anchor") >= 0


def test_the_dot_is_a_boundary_character():
    """The guard's whole reason for existing. If `.` is ever dropped
    from the name-continuation set, this is the line that says so."""
    assert edits._continues_a_name(".")
    assert edits._continues_a_name("_")
    assert edits._continues_a_name("'")
    assert not edits._continues_a_name(" ")
    assert not edits._continues_a_name("\n")


def test_the_regional_closing_anchor_is_covered_too(monkeypatch):
    """`replace_between`'s closing anchor searches from after the
    opening one. It goes through the same chokepoint, so the fix is
    one place and three anchor forms — verified rather than assumed."""
    opening = FILE.index("theorem")
    with pytest.raises(edits.EditError) as e:
        edits._find_unique(FILE, "end Problems", 0, "closing anchor",
                           start=opening, scope="after the opening anchor")
    assert "matches inside" in str(e.value)
