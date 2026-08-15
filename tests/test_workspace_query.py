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


# ── the DELIVERY budget: fit the transport by deferring, never by
#    cutting (2026-08-15) ────────────────────────────────────────────
#
# The codex exec channel hands the model ~10K tokens of tool output and
# amputates the middle of anything larger — a 90,417-char reply arrived
# as 39,700 chars with the mid-batch answers gone, and six Adversary
# spawns filed the same report in 50 minutes. The reply must fit the
# pipe HERE, where whole queries can still be deferred by name; the
# budget is per backend (`llm/capabilities.mcp_result_delivery_chars`)
# and None — an unmeasured backend — applies no ceiling.


def _three_reads(tmp_path):
    for name in ("a.md", "b.md", "c.md"):
        (tmp_path / name).write_text(name[0] * 3000 + "\n",
                                     encoding="utf-8")
    return [{"read": "a.md"}, {"read": "b.md"}, {"read": "c.md"}]


def test_overflow_defers_whole_queries_by_name(tmp_path):
    out = wq.run_queries(_three_reads(tmp_path), cwd=tmp_path,
                         delivery_chars=4000)
    assert len(out) <= 4000, "the reply itself must fit the transport"
    assert "aaa" in out, "the first answer is delivered"
    # the losers are whole, named queries — not amputated answers
    assert "bbb" not in out and "ccc" not in out
    assert "not answered" in out and "budget" in out
    assert "[2]" in out and "[3]" in out and "'read'" in out
    assert "Send these in a second call" in out


def test_delivered_answers_keep_their_full_per_query_budget(tmp_path):
    """The pooled-budget regression, pinned from the other side: a
    delivery ceiling must never shrink an answer it delivers."""
    out = wq.run_queries(_three_reads(tmp_path), cwd=tmp_path,
                         delivery_chars=4000)
    assert out.count("aaa") >= 1
    first = out.split("\n\n")[0]
    assert "truncated" not in first
    assert first.count("a") >= 3000, "the delivered answer arrives whole"


def test_every_block_is_complete_or_carries_its_own_notice(tmp_path):
    """The invariant the codex cut violated: a delivered block either
    ends because its answer ended, or says so itself."""
    (tmp_path / "huge.md").write_text("h" * 20000 + "\n", encoding="utf-8")
    (tmp_path / "tiny.md").write_text("needle\n", encoding="utf-8")
    out = wq.run_queries(
        [{"read": "huge.md"}, {"read": "tiny.md"}], cwd=tmp_path,
        per_query_chars=2000, delivery_chars=6000)
    assert len(out) <= 6000
    assert "[1] truncated at" in out, (
        "the per-query cut still names itself under a delivery budget")
    assert "needle" in out or "[2]" in out


def test_the_first_query_is_answered_even_alone_over_the_ceiling(tmp_path):
    (tmp_path / "big.md").write_text("q" * 5000 + "\n", encoding="utf-8")
    out = wq.run_queries([{"read": "big.md"}], cwd=tmp_path,
                         delivery_chars=1000)
    assert "qqq" in out, (
        "a reply that deferred everything would answer nothing — the "
        "first query rides whatever it costs")


def test_no_ceiling_means_no_deferral(tmp_path):
    """An UNMEASURED backend gets no cap — rationing a channel that
    delivers whole is the regression the owner ruled out."""
    out = wq.run_queries(_three_reads(tmp_path), cwd=tmp_path)
    assert "aaa" in out and "bbb" in out and "ccc" in out
    assert "not answered" not in out


def test_budget_and_count_deferrals_merge_into_one_resend_list(tmp_path):
    queries = _three_reads(tmp_path) + [{"size": "a.md"}]
    out = wq.run_queries(queries, cwd=tmp_path, max_queries=3,
                         delivery_chars=4000)
    assert len(out) <= 4000
    # one list, every missing query on it — [2] [3] by budget, [4] by
    # count; the agent resends one batch, not two reasons' worth
    assert out.count("Send these in a second call") == 1
    for tag in ("[2]", "[3]", "[4]"):
        assert tag in out


def test_the_deferral_note_itself_fits_the_budget(tmp_path):
    """The note is part of the reply; a budget met before the note and
    broken after it would re-open the exact hole being closed."""
    for i in range(6):
        (tmp_path / f"f{i}.md").write_text(("%d" % i) * 2500 + "\n",
                                           encoding="utf-8")
    queries = [{"read": f"f{i}.md"} for i in range(6)]
    # sized so two answers fit BEFORE the note and not after it — the
    # last delivered answer must be handed back whole, not trimmed
    out = wq.run_queries(queries, cwd=tmp_path, delivery_chars=5200)
    assert len(out) <= 5200
    assert "000" in out, "the first answer survives the hand-back"


# ── section misses and duplicate headings (2026-08-15) ──────────────


def test_a_sections_miss_carries_no_roster_only_the_count(tmp_path):
    """A miss on the 383-section CATALOG.md answered with an inlined
    roster that was itself a 12KB cap-hit — a refusal whose length
    scaled with the file. No roster at all (owner ruling 2026-08-15):
    `outline` already IS the roster, with line ranges and sizes; the
    refusal names the miss, the COUNT, and that action."""
    doc = "\n".join(f"## entry_{i:03d}\nbody {i}" for i in range(40))
    (tmp_path / "CATALOG.md").write_text(doc + "\n", encoding="utf-8")
    out = wq.run_queries(
        [{"read": "CATALOG.md", "sections": ["no_such_entry"]}],
        cwd=tmp_path)
    assert "no section named 'no_such_entry'" in out
    assert "40 sections" in out
    assert "outline" in out, "the refusal names the reachable action"
    assert "entry_000" not in out, "no roster — its length scaled"
    assert len(out) < 400


def test_duplicate_headings_are_disclosed_not_swallowed(tmp_path):
    """Stacked charters carry the same heading twice; a dict that keeps
    one of them silently answers with SOME section while the reader
    believes the name was unambiguous."""
    (tmp_path / "charter.md").write_text(
        "# Charter\n## The claim to settle\nfirst body\n"
        "## Above\n## The claim to settle\nsecond body\n",
        encoding="utf-8")
    out = wq.run_queries(
        [{"read": "charter.md", "sections": ["The claim to settle"]}],
        cwd=tmp_path)
    assert "first body" in out
    assert "2 sections share this heading" in out
    assert "lines 5-6" in out, "the other occurrence is named by lines"
