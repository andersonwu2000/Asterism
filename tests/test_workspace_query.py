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
    got "no such file" and spent its next turn running `ls`."""
    out = wq.run_queries([{"read": "prooofs/L_a.lean"}], cwd=here)
    assert "no file at" in out
    assert "nearest existing directory" in out
    assert "proofs/" in out and "Manifest.md" in out


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
