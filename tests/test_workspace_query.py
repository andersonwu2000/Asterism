"""`inspect` — the batch read tool that replaces 91% of the shell.

Shape comes from the survey, not from taste: 60% of current-era shell
calls chain two or more commands, 32% cap their own output with `head`,
12% separate sections with `echo`. So the contract under test is
"several questions, each capped, results labelled" — a stronger single
grep would have recovered none of that.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.knowledge import workspace_query as wq


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    """A workspace shaped like the real one: two problems, a Library, and
    the operator-private subtrees the read fence exists for."""
    (tmp_path / "Tooling").mkdir()
    p = tmp_path / "Problems" / "Combinatorics" / "union_closed"
    (p / "proofs").mkdir(parents=True)
    (p / "proofs" / "L_a.lean").write_text(
        "import Mathlib\ntheorem a_bound : 1 ≤ 2 := by norm_num\n",
        encoding="utf-8")
    (p / "proofs" / "L_b.lean").write_text(
        "import Mathlib\ntheorem b_bound : 2 ≤ 3 := by norm_num\n",
        encoding="utf-8")
    (p / "Manifest.md").write_text("# manifest\nline2\nline3\nline4\n",
                                   encoding="utf-8")
    other = tmp_path / "Problems" / "Topology" / "loops"
    other.mkdir(parents=True)
    (other / "secret.lean").write_text("theorem elsewhere : True := trivial\n",
                                       encoding="utf-8")
    (tmp_path / "docs" / "internal").mkdir(parents=True)
    (tmp_path / "docs" / "internal" / "STATUS.md").write_text(
        "operator notes\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def here(ws: Path) -> Path:
    return ws / "Problems" / "Combinatorics" / "union_closed"


def test_one_call_answers_several_questions(here: Path) -> None:
    out = wq.run_queries([
        {"grep": "theorem", "in": "proofs/*.lean"},
        {"read": "Manifest.md", "lines": "1-2"},
        {"size": "Manifest.md"},
    ], cwd=here)
    assert "[1] grep" in out and "[2] read" in out and "[3] size" in out
    assert "a_bound" in out and "b_bound" in out
    assert "# manifest" in out
    assert "4 lines" in out


def test_each_query_carries_its_own_cap_and_says_what_it_dropped(
    here: Path,
) -> None:
    """A cap that hides its own existence is the thing the "no silent
    truncation" rule forbids — the answer must name the count AND the
    way to see the rest."""
    out = wq.run_queries([{"grep": "theorem", "in": "proofs/*.lean",
                           "max": 1}], cwd=here)
    assert "… 1 more" in out
    assert "Re-run with max:" in out


def test_a_wrong_path_answers_with_what_is_actually_there(
    here: Path,
) -> None:
    """Before this, a mistyped path cost a whole round-trip: the agent
    got "no such file" and spent its next turn running `ls`.

    `read` now gets the same answer `grep` already got — the file's REAL
    path, when one of that name exists (2026-08-15; the two had drifted,
    and the weaker of the two answers was the one on the hotter query).
    The directory-listing fallback for a name that exists nowhere is
    pinned in `test_inspect_path_answers.py`."""
    out = wq.run_queries([{"read": "prooofs/L_a.lean"}], cwd=here)
    assert "no file at" in out
    assert "use that path" in out
    assert "proofs" in out and "L_a.lean" in out


def test_the_read_fence_is_the_same_one_every_channel_uses(
    here: Path,
) -> None:
    """One list (`envelope.read_deny_roots`), rendered for agy, for
    spawn_guard, and here. A second copy is how the two drift apart."""
    out = wq.run_queries([
        {"read": "../../../docs/internal/STATUS.md"},
        {"read": "../../Topology/loops/secret.lean"},
    ], cwd=here)
    assert "operator-private" in out
    assert "operator notes" not in out
    assert "theorem elsewhere" not in out


def test_grep_skips_denied_files_without_failing_the_query(
    here: Path,
) -> None:
    """A search rooted where it is allowed must not die because the tree
    contains something private — it just does not report it."""
    out = wq.run_queries([{"grep": "theorem", "in": "../.."}], cwd=here)
    assert "a_bound" in out
    assert "theorem elsewhere" not in out


def test_paths_come_back_with_forward_slashes(here: Path) -> None:
    """They get pasted into imports, into the next query and into prose;
    a stray `proofs\\L_a.lean` reads as an escape sequence."""
    out = wq.run_queries([{"find": "*.lean"}], cwd=here)
    assert "proofs/L_a.lean" in out
    assert "\\" not in out


def test_line_ranges_are_numbered(here: Path) -> None:
    out = wq.run_queries([{"read": "Manifest.md", "lines": "2-3"}], cwd=here)
    assert "2  line2" in out and "3  line3" in out
    assert "# manifest" not in out


def test_an_unknown_key_teaches_the_vocabulary(here: Path) -> None:
    """A gate message names the way out (07-31 lesson) — here, the five
    keys, because the agent cannot see the schema."""
    out = wq.run_queries([{"cat": "Manifest.md"}], cwd=here)
    assert "no known query key" in out
    for key in ("decl", "grep", "read", "find", "size"):
        assert key in out


def test_one_broken_query_does_not_lose_the_others(here: Path) -> None:
    out = wq.run_queries([
        {"grep": "([unclosed", "in": "proofs/*.lean"},
        {"size": "Manifest.md"},
    ], cwd=here)
    assert "bad pattern" in out
    assert "4 lines" in out


def test_decl_degrades_without_a_database(here: Path) -> None:
    """`decl` answers from the framework's tables. With no database it
    must say so rather than silently returning "not found", which an
    agent would read as "that declaration does not exist"."""
    out = wq.run_queries([{"decl": "a_bound"}], cwd=here)
    assert "unavailable" in out or "no declaration named" in out


# ── the budget is per query, not per call (2026-08-13 / 08-15) ──────
#
# `inspect` asks for a batch — the argument is a list and the help text
# shows two questions — and a single cap used to fall across the
# concatenation. The last questions in a batch lost answers that had
# already been computed, under one footer reading "whole result
# truncated" that named none of them: the agent could tell something
# was missing but not WHICH, so the only recovery was to re-ask
# everything one at a time.
#
# 08-13 divided the cap instead of sharing it (`8000 // len(queries)`),
# which fixed the anonymity and left the pricing: a batch still shrank
# its own answers, so a third question cost the first two a third of
# their content each. On the 08-15 codex probe 24 of 51 calls carried
# exactly ONE query and 24 of 51 answers came back truncated — the
# agent had read the price list correctly. The budget is now per query
# and NOT a pool, and the call-level limit is a query COUNT that defers
# whole questions by name.


def test_one_greedy_query_cannot_eat_a_later_answer(tmp_path):
    here = tmp_path
    (here / "big.lean").write_text("x" * 5000 + "\n", encoding="utf-8")
    (here / "small.lean").write_text("needle here\n", encoding="utf-8")
    out = wq.run_queries(
        [{"read": "big.lean"}, {"grep": "needle", "in": "*.lean"}],
        cwd=here, per_query_chars=2000)
    assert "needle" in out, (
        "the second query's answer was computed and then thrown away by "
        "the first query's size — that is the bug this pins")


def test_a_truncated_query_names_itself_and_the_way_back(tmp_path):
    here = tmp_path
    (here / "big.lean").write_text("y" * 9000 + "\n", encoding="utf-8")
    out = wq.run_queries([{"read": "big.lean"}, {"decl": "nope"}],
                         cwd=here, per_query_chars=2000)
    assert "[1] truncated at" in out, "the cut must name which query it cut"
    # "Re-run THIS query alone" was the old way back, and it was not a
    # way back at all: it re-sends every line the reader has already
    # paid for. The numbered output makes the continuation exact.
    assert "Continue from line" in out, (
        "a truncation notice has to name an action the reader can take")
    assert "Re-run THIS query alone" not in out


def test_a_single_query_still_gets_the_whole_budget(tmp_path):
    here = tmp_path
    (here / "big.lean").write_text("z" * 5000 + "\n", encoding="utf-8")
    out = wq.run_queries([{"read": "big.lean"}], cwd=here,
                         per_query_chars=4000)
    assert len(out) > 3500, (
        "dividing the budget must not penalise the un-batched case")
