"""Anchored edit resolution — the class-ending property under test.

The property is not "edits land in the right place". It is: **when the
agent's model of the file is stale, nothing happens.** Line ranges could
not offer that — every in-bounds range is valid, so a stale coordinate
spliced silently. 42 of 597 agent reports in one week were that one
shape.
"""
from __future__ import annotations

import pytest

from Tooling.lsp import edits as E

FILE = """import Mathlib
namespace Problems.T.p

theorem a_bound : 1 ≤ 2 := by
  norm_num

theorem b_bound : 2 ≤ 3 := by
  norm_num

end Problems.T.p
"""


def _apply(content, spec):
    return E.apply_spans(content, E.resolve(content, spec))


# ------------------------------------------------ it does the job

def test_a_unique_anchor_is_replaced() -> None:
    out = _apply(FILE, [{"replace": "theorem a_bound : 1 ≤ 2",
                         "with": "theorem a_bound : 1 ≤ 3"}])
    assert "1 ≤ 3" in out and "b_bound" in out
    assert out.endswith("end Problems.T.p\n")


def test_a_batch_applies_in_one_pass() -> None:
    out = _apply(FILE, [
        {"replace": "1 ≤ 2", "with": "1 ≤ 9"},
        {"replace": "2 ≤ 3", "with": "2 ≤ 8"},
        {"insert_after": "import Mathlib", "text": "\n-- note"},
    ])
    assert "1 ≤ 9" in out and "2 ≤ 8" in out and "-- note" in out


def test_replace_between_spans_a_block_without_quoting_it() -> None:
    """Requiring the whole 40-line tactic block verbatim would create a
    new failure class — transcription slips reading as no-match.

    Both `norm_num`s follow `theorem a_bound`, so the bare tactic line
    is an ambiguous closing anchor here (see the refusal test below).
    One line of context — the tool's own advice — is what it costs to
    disambiguate, NOT the whole block. That distinction is the whole
    argument for keeping this form."""
    out = _apply(FILE, [{"replace_between": ["theorem a_bound",
                                             "1 ≤ 2 := by\n  norm_num"],
                         "with": "theorem a_bound : True := trivial"}])
    assert "theorem a_bound : True := trivial" in out
    assert "b_bound" in out                     # the NEXT block survived
    assert out.count("norm_num") == 1


def test_insert_after_a_full_line_starts_its_own_line() -> None:
    """The two glue repairs agents paid on 2026-08-16: a comment after
    `…false in` became `in-- note`, and an import after `import Mathlib`
    became `import Mathlibimport X`. An anchor that ends its line gets
    the new text on a new line; text carrying its own newline is
    untouched (the batch test above passes "\\n-- note" and stays as
    written)."""
    out = _apply(FILE, [{"insert_after": "import Mathlib",
                         "text": "import X"}])
    assert "import Mathlib\nimport X\n" in out
    assert "Mathlibimport" not in out


def test_insert_after_mid_line_stays_verbatim() -> None:
    """A mid-line anchor is the inline use — the caller's own spacing,
    not the tool's to editorialize."""
    out = _apply(FILE, [{"insert_after": "theorem a_bound",
                         "text": "'"}])
    assert "theorem a_bound' : 1 ≤ 2" in out


def test_closing_anchor_need_only_be_unique_after_the_opening_one() -> None:
    """`norm_num` occurs twice in the file, and the span still resolves:
    only ONE of them follows `theorem b_bound`. The closing anchor is
    regional, never global — demanding global uniqueness would push the
    agent back to quoting whole blocks."""
    out = _apply(FILE, [{"replace_between": ["theorem b_bound", "norm_num"],
                         "with": "theorem b_bound : True := trivial"}])
    assert "theorem b_bound : True := trivial" in out
    assert "a_bound" in out and "norm_num" in out


# ------------------------------- and refuses rather than guessing

def test_a_missing_anchor_refuses_and_nothing_is_applied() -> None:
    with pytest.raises(E.EditError) as ei:
        E.resolve(FILE, [{"replace": "theorem c_bound", "with": "x"}])
    assert "does not appear" in ei.value.message


def test_an_ambiguous_anchor_refuses_and_names_every_line() -> None:
    with pytest.raises(E.EditError) as ei:
        E.resolve(FILE, [{"replace": "  norm_num", "with": "  simp"}])
    assert "appears 2" in ei.value.message
    assert ei.value.extra["match_lines"] == [5, 8]


def test_a_whitespace_only_mismatch_returns_the_verbatim_text() -> None:
    """Never applied automatically — this is Lean and indentation is
    semantic. Quoting the real text makes the retry mechanical."""
    with pytest.raises(E.EditError) as ei:
        E.resolve(FILE, [{"replace": "theorem  a_bound  :  1 ≤ 2",
                          "with": "x"}])
    assert "whitespace" in ei.value.message
    assert ei.value.extra["closest_region"].strip().startswith("theorem a_bound")


def test_one_bad_edit_fails_the_whole_batch() -> None:
    """All-or-nothing. A partial batch would leave the agent unable to
    say which of two files it is now editing — the exact state-tracking
    burden this design exists to remove."""
    with pytest.raises(E.EditError) as ei:
        E.resolve(FILE, [
            {"replace": "1 ≤ 2", "with": "1 ≤ 9"},
            {"replace": "nowhere to be found", "with": "x"},
        ])
    assert ei.value.index == 2


def test_overlapping_edits_refuse_and_name_both() -> None:
    with pytest.raises(E.EditError) as ei:
        E.resolve(FILE, [
            {"replace": "theorem a_bound : 1 ≤ 2 := by\n  norm_num",
             "with": "x"},
            {"replace": "1 ≤ 2", "with": "y"},
        ])
    assert "overlaps edit 1" in ei.value.message


def test_an_unknown_key_teaches_the_three_forms() -> None:
    with pytest.raises(E.EditError) as ei:
        E.resolve(FILE, [{"line": 4, "with": "x"}])
    for form in ("replace", "replace_between", "insert_after"):
        assert form in ei.value.message


def test_there_is_no_way_to_address_by_line_number() -> None:
    """The property that ends the class: a line number cannot be
    expressed in a request, so it cannot be stale. Line numbers survive
    only in OUTPUT, where the tool measured them."""
    import inspect
    src = inspect.getsource(E.resolve)
    assert "start_line" not in src and "end_line" not in src


# --------------------------------------------------- the tail case

def test_replacing_the_last_block_keeps_what_follows() -> None:
    """Two of the loudest complaints — a dropped `end` and a duplicated
    proof body — were both whole-tail splices. An anchored span cannot
    reach past its closing anchor."""
    out = _apply(FILE, [{"replace_between": ["theorem b_bound", "  norm_num"],
                         "with": "theorem b_bound : True := trivial"}])
    assert out.rstrip().endswith("end Problems.T.p")
    assert out.count("end Problems.T.p") == 1


# ------------- the closing anchor stopped guessing (2026-08-11)
#
# It was the one address in this API that resolved ambiguously: it took
# the FIRST match after the opening anchor and said nothing. When the
# intended occurrence failed to match verbatim — one space of
# indentation is enough — it bound to a LATER one and the span swallowed
# everything in between. Reported from production as "deleted the e1/e2
# have-blocks that followed, leaving a dangling `intro h` and unknown
# identifiers". The echo that would have shown the damage is capped at
# 200 characters, and the evidence of over-reach lives at the END of the
# span, so the agent had no way to see it.

def test_an_ambiguous_closing_anchor_refuses_instead_of_taking_the_first(
) -> None:
    """Two `norm_num`s follow `theorem a_bound`. The tool cannot know
    which one was meant, and guessing is what corrupted files — so it
    refuses, the same way the opening anchor has always refused."""
    with pytest.raises(E.EditError) as ei:
        E.resolve(FILE, [{"replace_between": ["theorem a_bound", "norm_num"],
                          "with": "x"}])
    assert "closing anchor" in ei.value.message
    assert "appears 2" in ei.value.message


def test_the_refusal_names_the_rival_lines_and_the_way_out() -> None:
    """A refusal without an exit is a wall the agent hits twice: it must
    point at the competing matches and say what to do about them."""
    with pytest.raises(E.EditError) as ei:
        E.resolve(FILE, [{"replace_between": ["theorem a_bound", "norm_num"],
                          "with": "x"}])
    assert ei.value.extra["match_lines"] == [5, 8]
    assert "extend it until it is unique" in ei.value.message
    # and it must say WHERE it looked, or "appears 2 times" reads as a
    # claim about the whole file — which would be false, and would send
    # the agent hunting for a match that is not the tool's problem.
    assert "after the opening anchor" in ei.value.message


def test_a_matchless_closing_anchor_says_where_it_looked() -> None:
    """`import Mathlib` exists, but not after the opening anchor. The
    old message said "does not appear after the opening one"; the new
    one must not regress into claiming it is absent from the file."""
    with pytest.raises(E.EditError) as ei:
        E.resolve(FILE, [{"replace_between": ["theorem b_bound",
                                              "import Mathlib"],
                          "with": "x"}])
    assert "after the opening anchor" in ei.value.message


def test_a_refused_batch_changes_nothing() -> None:
    """All-or-nothing is what makes the retry safe — and it is the whole
    reason refusing beats guessing here: a wrong address now costs a
    round trip instead of a reconstruction."""
    # Deliberately NON-overlapping: an overlapping pair would be refused
    # by the overlap check no matter what the closing anchor did, and
    # the test would pass for a reason unrelated to the one it names.
    spec = [{"replace": "2 ≤ 3", "with": "2 ≤ 8"},
            {"replace_between": ["theorem a_bound", "norm_num"], "with": "x"}]
    with pytest.raises(E.EditError) as ei:
        E.resolve(FILE, spec)
    assert ei.value.index == 2          # the closing anchor, not the pair
    # and the sound edit is untouched, so resubmitting it costs nothing
    assert _apply(FILE, spec[:1]).count("2 ≤ 8") == 1
