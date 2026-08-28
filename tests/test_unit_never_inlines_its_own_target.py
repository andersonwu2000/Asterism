"""A file is not its own sibling.

WHAT THIS COSTS WHEN IT IS WRONG. The gateway assembles one compilation
unit from the file being edited plus the `new_<slug>.lean` stubs that
file references. The Forward seat's target is itself a `new_*.lean`
(`new_forward.lean`), and the self-exclusion test asked the wrong
question — "does this content DECLARE `forward`", which is true for
Backward, whose stub file and theorem share a name, and never true for
Forward, whose theorem is whatever the agent invented.

Two more things had to line up, and both did. The reference test is a
bare word match over the whole text INCLUDING COMMENTS. And the word
was put there by the framework itself: `pipeline/forward.py` seeds the
file with `-- Write ONE forward lemma here`. So the target's disk copy
was inlined ahead of the live content, the unit carried the agent's
declaration twice, and every `errors_at` / `goal_at` / `apply_edit`
answered "has already been declared" about the line just written —
while `validate_file`, given the agent's pasted text without the
scaffold comment, saw nothing to inline and said the file was clean.
Two tools, one worker, one builder, different bytes.

Latent since 2026-06-18. 45 reports on 08-13/14 alone, every one from
the Forward seat, none from Backward. Four earlier fixes aimed at slot
cache validity, which is a real subsystem and was not this.

These tests are pure text — no Lean, no LSP, milliseconds — because the
property is about which files go into the unit, and that is decidable
without elaborating anything.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.lsp import gateway


SEED = ("-- Write ONE forward lemma here (see your instructions). Edit "
        "this file with\n-- apply_edit.\n")


@pytest.mark.parametrize("target,decl", [
    # Forward: target IS a new_*.lean, and its theorem name is not its
    # slug. This is the combination that shipped broken.
    ("new_forward.lean", "theorem uc_634_two_pole_f2_le_f4"),
    # A hypothetical future seat with the same shape — the guard must
    # not be spelled for one filename.
    ("new_mint.lean", "theorem some_invented_name"),
])
def test_the_target_is_never_inlined_into_its_own_unit(
        tmp_path: Path, target: str, decl: str):
    (tmp_path / target).write_text(f"{SEED}{decl} : True := trivial\n",
                                   encoding="utf-8")
    content = (tmp_path / target).read_text(encoding="utf-8")

    got = gateway._collect_referenced_sibling_stubs(
        tmp_path, content, own_name=target)

    assert got == [], (
        f"{target} was inlined into its own compilation unit — the unit "
        f"now declares {decl.split()[1]} twice and every tool will call "
        f"it 'already declared'")


def test_a_real_sibling_still_comes_in(tmp_path: Path):
    """The exclusion is by file identity, so it must not cost the
    feature: a stub the content actually cites is still inlined."""
    (tmp_path / "new_forward.lean").write_text(
        f"{SEED}theorem head : True := by exact helper_lemma\n",
        encoding="utf-8")
    (tmp_path / "new_helper_lemma.lean").write_text(
        "theorem helper_lemma : True := trivial\n", encoding="utf-8")
    content = (tmp_path / "new_forward.lean").read_text(encoding="utf-8")

    got = gateway._collect_referenced_sibling_stubs(
        tmp_path, content, own_name="new_forward.lean")

    assert [s for s, _ in got] == ["helper_lemma"], got


def test_both_entry_points_build_the_same_bytes(tmp_path: Path,
                                                monkeypatch):
    """One builder is the property `21d83f63` established and nothing
    guarded: given the same content and the same stub set, the session
    tools' unit and `validate_file`'s unit must be byte-identical. When
    they are not, the two answers can differ with nobody at fault."""
    (tmp_path / "new_forward.lean").write_text(
        f"{SEED}theorem head : True := trivial\n", encoding="utf-8")
    (tmp_path / "new_side.lean").write_text(
        "theorem side : True := trivial\n", encoding="utf-8")
    content = (tmp_path / "new_forward.lean").read_text(encoding="utf-8")

    # (A `_framework_prefix_lines` patch with raising=False sat here for
    # months — the symbol never existed anywhere in Tooling, so it set a
    # dead attribute and guarded nothing. Removed 2026-08-29.)
    a = gateway._build_compilation_unit(
        content, "P", tmp_path, tmp_path, own_name="new_forward.lean")
    b = gateway._build_compilation_unit(
        content, "P", tmp_path, tmp_path, own_name="new_forward.lean")
    assert a[0] == b[0] and a[1] == b[1], (
        "the same inputs produced two different units")


def test_the_fingerprint_ignores_the_targets_own_edits(tmp_path: Path):
    """`_stub_fingerprint` answers "did a SIBLING change under me". It
    used to include the target, so on the Forward seat every write-
    through invalidated the slot and the next read re-elaborated what
    had just been elaborated — a cold rebuild per edit, forever."""
    (tmp_path / "new_forward.lean").write_text("v1\n", encoding="utf-8")
    (tmp_path / "new_side.lean").write_text("s\n", encoding="utf-8")

    before = gateway._stub_fingerprint(tmp_path, "new_forward.lean")
    (tmp_path / "new_forward.lean").write_text("v2 longer\n",
                                               encoding="utf-8")
    after = gateway._stub_fingerprint(tmp_path, "new_forward.lean")
    assert before == after, "editing the target moved the sibling fingerprint"

    (tmp_path / "new_side.lean").write_text("s changed\n", encoding="utf-8")
    assert gateway._stub_fingerprint(tmp_path, "new_forward.lean") != after, (
        "a real sibling change must still invalidate")
