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
from Tooling.state import db as _db


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
    truncation" rule forbids — the answer must disclose that more exist
    AND hand back the way to see the rest. (Since the 2026-08-23 stall
    fix the scan STOPS at max+1 hits, so the exact remainder is unknown
    by design; the `after` handle replaces the "re-run with max" hint.)"""
    out = wq.run_queries([{"grep": "theorem", "in": "proofs/*.lean",
                           "max": 1}], cwd=here)
    assert "more exist" in out
    assert 'after: "' in out


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


def _seed_decl(ws: Path, here: Path, *, slug: str, sig_lines: int) -> None:
    """A minimal `asterism.db` + on-disk stub carrying one goal, so
    `_q_decl` resolves `slug` to a REAL full signature the way
    `goal_display_signature` reads it (from the stub file, not the
    stored `statement`) — see the "flattening" note at `_q_decl`'s
    top. `sig_lines` binder lines put the rendered signature exactly
    at the size under test."""
    rel = f"proofs/L_{slug}.lean"
    binders = "\n".join(f"    (h{i} : True)" for i in range(sig_lines))
    (here / "proofs" / f"L_{slug}.lean").write_text(
        f"import Mathlib\ntheorem {slug}\n{binders}\n    : True := by\n"
        f"  trivial\n", encoding="utf-8")
    conn = _db.connect(ws / "asterism.db")
    _db.init_schema(conn)
    conn.execute(
        "INSERT INTO problems (name, created_at, bootstrap_done)"
        " VALUES (?, ?, 1)", ("union_closed", _db.now()))
    _db.insert_goal(
        conn, problem="union_closed", slug=slug,
        lean_path=f"Problems/Combinatorics/union_closed/{rel}",
        statement="True", origin="root")
    conn.close()


def test_decl_signature_over_16_lines_names_the_elided_count_and_the_way_back(
    ws: Path, here: Path,
) -> None:
    """The old `splitlines()[:16]` cut carried no note at all — ~26 agent
    reports of a declaration that "stopped mid-definition" with nothing
    telling them more existed. Truncation is a VIEW, never a loss: the
    note must name the count AND a reachable action (the sibling `grep`
    path already discloses its own cut; `decl` must match it)."""
    _seed_decl(ws, here, slug="long_sig", sig_lines=20)
    out = wq.run_queries([{"decl": "long_sig"}], cwd=here)
    assert "more line(s) elided" in out
    # The way back must be reachable: `read` + `lines` on the SAME file
    # path the decl answer already printed, picking up right after the
    # 16 lines shown.
    assert '"lines": "17-"' in out
    assert "L_long_sig.lean" in out


def test_decl_signature_at_16_lines_or_fewer_has_no_truncation_note(
    ws: Path, here: Path,
) -> None:
    """A signature that already fits whole must not carry a note about a
    cut that never happened — that would be its own false signal."""
    _seed_decl(ws, here, slug="short_sig", sig_lines=1)
    out = wq.run_queries([{"decl": "short_sig"}], cwd=here)
    assert "elided" not in out


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
    # `lines` is a deliberate window, so the clip path still applies
    # there; a bare whole read of an oversize file is refused instead
    # (2026-08-18, tested separately).
    out = wq.run_queries([{"read": "big.lean", "lines": "1-"},
                          {"decl": "nope"}],
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
    out = wq.run_queries([{"read": "big.lean", "lines": "1-"}], cwd=here,
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
    assert '[2] {"read": "b.md"}' in out and '[3] {"read": "c.md"}' in out
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
        [{"read": "huge.md", "lines": "1-"}, {"read": "tiny.md"}],
        cwd=tmp_path,
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


# ---------------------------------------------------------------------
# Whose file is it? (2026-08-16)
#
# A spawn's cwd is its PROBLEM dir, but its briefing — Context.md,
# CATALOG.md, the seeded `new_*.lean` — is written into its ATTEMPTS
# dir. A bare `read: "Context.md"` therefore missed, and the fallback
# scanned the whole `.attempts/` tree and returned whatever sorted
# first: another live spawn's file, complete and plausible and not this
# agent's. 43 self-reports on 2026-08-15 alone; a formalizer read one
# attempt's `new_forward.lean` while the LSP edited its own, which is
# how an edit lands on the wrong theorem.
# ---------------------------------------------------------------------

@pytest.fixture
def spawn(tmp_path: Path, monkeypatch) -> "tuple[Path, Path, Path]":
    """cwd = problem dir; mine + theirs = two sibling attempt dirs."""
    (tmp_path / "Tooling").mkdir()
    cwd = tmp_path / "Problems" / "Combinatorics" / "union_closed"
    cwd.mkdir(parents=True)
    attempts = tmp_path / ".attempts"
    # `aaaa…` sorts FIRST — the old scan would always have picked it.
    theirs = attempts / "aaaa1111-0000-0000-0000-000000000000"
    mine = attempts / "zzzz9999-0000-0000-0000-000000000000"
    for d in (theirs, mine):
        d.mkdir(parents=True)
    (theirs / "Context.md").write_text(
        "## TREE\n\nsomeone else's programme\n", encoding="utf-8")
    (mine / "Context.md").write_text(
        "## TREE\n\nmy own programme\n", encoding="utf-8")
    (theirs / "new_forward.lean").write_text(
        "theorem theirs : True := trivial\n", encoding="utf-8")
    (mine / "new_forward.lean").write_text(
        "theorem mine : True := trivial\n", encoding="utf-8")
    monkeypatch.setenv("ASTERISM_SPAWN_WRITE_ROOTS", str(mine))
    return cwd, mine, theirs


def test_a_bare_framework_filename_resolves_to_my_own_attempt(spawn):
    cwd, mine, theirs = spawn
    out = wq.run_queries([{"read": "Context.md"}], cwd=cwd)
    assert "my own programme" in out
    assert "someone else's programme" not in out


def test_a_seeded_lean_file_is_mine_not_the_sibling_that_sorts_first(spawn):
    """The severe shape: `inspect` reads one attempt's seed while the LSP
    edits this spawn's own sandbox."""
    cwd, mine, theirs = spawn
    out = wq.run_queries([{"read": "new_forward.lean"}], cwd=cwd)
    assert "theorem mine" in out and "theorem theirs" not in out
    out = wq.run_queries(
        [{"grep": "theorem", "in": "new_forward.lean"}], cwd=cwd)
    assert "theorem mine" in out and "theorem theirs" not in out


def test_a_miss_never_points_at_another_spawns_file(spawn):
    """The hint searched every attempt, so a typo was answered with a
    stranger's file and the words `use that path`. Better silent."""
    cwd, mine, theirs = spawn
    (theirs / "only_theirs.md").write_text("not yours\n", encoding="utf-8")
    out = wq.run_queries([{"read": "only_theirs.md"}], cwd=cwd)
    assert "no file at" in out
    assert str(theirs) not in out
    assert "use that path" not in out


def test_outside_a_spawn_nothing_reaches_into_attempts(tmp_path, monkeypatch):
    """No write-roots env (operator shell, tests) → cwd only. The old
    code walked up to `.attempts/` regardless of who was asking."""
    monkeypatch.delenv("ASTERISM_SPAWN_WRITE_ROOTS", raising=False)
    (tmp_path / "Tooling").mkdir()
    cwd = tmp_path / "Problems" / "P" / "p"
    cwd.mkdir(parents=True)
    stray = tmp_path / ".attempts" / "abcd"
    stray.mkdir(parents=True)
    (stray / "Context.md").write_text("stray\n", encoding="utf-8")
    out = wq.run_queries([{"read": "Context.md"}], cwd=cwd)
    assert "stray" not in out and "no file at" in out


def test_a_deferred_query_comes_back_resendable(tmp_path):
    """`sorted(d)` on a dict yields its KEYS, so the one continuation
    cue read `[11] ['read', 'sections']` — the reader could not tell
    which file it had asked about, and "send these in a second call"
    was unfollowable. Three agents reported it within an hour of the
    deferral shipping (2026-08-15)."""
    (tmp_path / "a.md").write_text("x" * 9000, encoding="utf-8")
    (tmp_path / "charter.md").write_text(
        "## Proof\nbody\n", encoding="utf-8")
    out = wq.run_queries(
        [{"read": "a.md"},
         {"read": "charter.md", "sections": ["Proof"]}],
        cwd=tmp_path, delivery_chars=9_050)
    assert "not answered" in out
    assert '"read": "charter.md"' in out, out[-300:]
    assert '"sections": ["Proof"]' in out, "the selector must survive too"
    assert "['read', 'sections']" not in out


# ---------------------------------------------------------------------
# The delivery budget is a CONTRACT, not an aspiration (2026-08-16).
#
# Nothing pinned "the reply fits `delivery_chars`", and that gap let a
# regression ship the same day it was written: echoing the deferred
# query made the note's size a function of the QUERY's size, so a batch
# carrying long grep patterns produced a note bigger than the reply it
# was appended to — 41,747 chars of note against a 30,000-char budget,
# with the answers starved from 9 to 2. Found by an independent
# verifier, not by this suite.
# ---------------------------------------------------------------------

@pytest.mark.parametrize("pattern_len", [0, 500, 2_000, 40_000])
def test_the_reply_never_exceeds_its_delivery_budget(tmp_path, pattern_len):
    for i in range(12):
        (tmp_path / f"f{i}.md").write_text("body\n" * 400, encoding="utf-8")
    qs = [{"read": f"f{i}.md"} for i in range(9)]
    qs += [{"grep": "z" * pattern_len, "in": f"f{i}.md"} for i in range(9, 12)]
    out = wq.run_queries(qs, cwd=tmp_path, delivery_chars=30_000)
    assert len(out) <= 30_000, (
        f"{len(out):,} chars against a 30,000-char budget "
        f"(pattern_len={pattern_len:,})")


def test_a_long_query_does_not_starve_the_answers(tmp_path):
    """The note is an ADDRESS, not the payload: bounding each echo keeps
    the number of delivered answers independent of how long the deferred
    queries happen to be."""
    for i in range(12):
        (tmp_path / f"f{i}.md").write_text("body\n" * 400, encoding="utf-8")
    def delivered(pattern_len):
        qs = [{"read": f"f{i}.md"} for i in range(9)]
        qs += [{"grep": "z" * pattern_len, "in": f"f{i}.md"}
               for i in range(9, 12)]
        out = wq.run_queries(qs, cwd=tmp_path, delivery_chars=30_000)
        return sum(1 for i in range(9) if f"[{i + 1}] read" in out)
    assert delivered(40_000) == delivered(0)


def test_every_deferred_query_is_echoed_as_valid_json(tmp_path):
    """A bare string or a list is an accepted (if mistaken) query — the
    tool answers it — so it can also be deferred, and it used to come
    back as a Python repr: `['read', 'b.md']`, the exact shape this note
    exists to stop producing."""
    import json as _json
    (tmp_path / "x.md").write_text("hello\n", encoding="utf-8")
    qs = [{"read": "x.md"} for _ in range(20)]
    qs += ["Context.md", ["read", "b.md"], None]
    out = wq.run_queries(qs, cwd=tmp_path, max_queries=20)
    tail = out.split("second call:")[-1]
    assert "['read', 'b.md']" not in tail
    for chunk in tail.split(";"):
        payload = chunk.split("] ", 1)[1].strip() if "] " in chunk else ""
        if payload:
            _json.loads(payload)  # raises if not resendable


def test_dot_dot_cannot_walk_from_my_attempt_into_a_siblings(spawn):
    """Resolving against the attempt dir opened a second door, and
    `../<other-pid>/new_forward.lean` walked through it into exactly the
    file this resolution exists to keep out (found by an independent
    verifier, 2026-08-16)."""
    cwd, mine, theirs = spawn
    out = wq.run_queries(
        [{"read": f"../{theirs.name}/new_forward.lean"}], cwd=cwd)
    assert "theorem theirs" not in out
    assert "no file at" in out


def test_a_glob_cannot_walk_from_my_attempt_into_a_siblings(spawn):
    """The GLOB spelling of the same escape: `_expand`'s attempt-dir
    fallback skipped the containment check `_resolve` applies, so
    `in: "../<other-pid>/*.lean"` still served a sibling's files after
    the literal path was fixed (acceptance pass, 2026-08-17)."""
    cwd, mine, theirs = spawn
    out = wq.run_queries(
        [{"grep": "theorem", "in": f"../{theirs.name}/*.lean"}], cwd=cwd)
    assert "theorem theirs" not in out
    assert str(theirs) not in out
    # The legitimate fallback is untouched: a bare glob still answers
    # from THIS spawn's attempt.
    out2 = wq.run_queries([{"grep": "theorem", "in": "*.lean"}], cwd=cwd)
    assert "theorem mine" in out2 and "theorem theirs" not in out2


def test_the_deferral_note_is_bounded_by_count_too(tmp_path):
    """Bounding each echo fixed the query-SIZE vector; the note's length
    was still a function of the deferred COUNT — 1 read + 400 greps
    produced an 88,043-char reply against a 30,000-char budget, ~200
    chars of ticket per deferred query with no aggregate ceiling
    (acceptance pass, 2026-08-17). Echoes past the note's own budget
    collapse to an index range; the caller still holds the list it
    sent."""
    (tmp_path / "x.md").write_text("hello\n", encoding="utf-8")
    qs = [{"read": "x.md"}]
    qs += [{"grep": "z" * 150, "in": "x.md"} for _ in range(400)]
    out = wq.run_queries(qs, cwd=tmp_path, delivery_chars=30_000)
    assert len(out) <= 30_000, f"{len(out):,} chars against 30,000"
    assert "more — queries [" in out, "the way back must survive the cut"


def test_write_file_lands_in_my_own_attempt(spawn):
    """The server-side write that bypasses codex's Windows sandbox —
    whose per-session first write blocked 142.6s (measured 2026-08-17,
    growing day over day) so agents gave up and wakes died as
    `agent_no_output`. Bare names and the absolute paths the prompts
    hand out both land in THIS spawn's attempts dir."""
    cwd, mine, theirs = spawn
    out = wq.run_write("decision.json", '[{"kind": "Noop"}]')
    assert out.startswith("wrote 18 chars to")
    assert (mine / "decision.json").read_text(encoding="utf-8") == \
        '[{"kind": "Noop"}]'
    out2 = wq.run_write(str(mine / "proposal.md"), "# T\n")
    assert out2.startswith("wrote")
    assert (mine / "proposal.md").is_file()
    out3 = wq.run_write("decision.json", "[]")
    assert "replaced the previous version" in out3
    assert (mine / "decision.json").read_text(encoding="utf-8") == "[]"


def test_write_file_refuses_everywhere_else(spawn):
    """Not the problem dir (the stale-stray class #218), not a sibling
    attempt — and the refusal names the address that would work."""
    cwd, mine, theirs = spawn
    out = wq.run_write(str(cwd / "decision.json"), "[]")
    assert "only your attempts directory is writable" in out
    assert not (cwd / "decision.json").exists()
    out2 = wq.run_write(f"../{theirs.name}/new_forward.lean", "theorem x")
    assert "only your attempts directory is writable" in out2
    assert (theirs / "new_forward.lean").read_text(
        encoding="utf-8") == "theorem theirs : True := trivial\n"


def test_write_file_outside_a_spawn_refuses(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTERISM_SPAWN_WRITE_ROOTS", raising=False)
    monkeypatch.delenv("ASTERISM_SPAWN_ATTEMPT_DIR", raising=False)
    out = wq.run_write("x.txt", "y")
    assert "no attempts directory is declared" in out


def test_a_stale_first_write_root_does_not_switch_resolution_off(
        spawn, monkeypatch):
    """The loop tried one entry and returned — a first path that no
    longer exists took the whole mechanism down silently."""
    cwd, mine, theirs = spawn
    import os as _os
    monkeypatch.setenv("ASTERISM_SPAWN_WRITE_ROOTS",
                       str(cwd / "gone") + _os.pathsep + str(mine))
    monkeypatch.delenv("ASTERISM_SPAWN_ATTEMPT_DIR", raising=False)
    out = wq.run_queries([{"read": "Context.md"}], cwd=cwd)
    assert "my own programme" in out


def test_raw_read_round_trips_byte_identical(tmp_path):
    """2026-08-18 (57-entry cluster, the slice's largest): the decorated
    default forced hand-stripping of `NNNNN  ` prefixes before any
    write-back, and one agent's full-overwrite pasted the presentation
    header into proposal.md and lost content. `raw: true` returns the
    content undecorated — whole file, `lines` windows, and `sections`
    alike — so read→write_file round-trips without surgery."""
    body = "# T\n\nalpha\n  indented line\n\n## Sec\nbeta\n"
    (tmp_path / "doc.md").write_text(body, encoding="utf-8")

    out = wq.run_queries([{"read": "doc.md", "raw": True}], cwd=tmp_path)
    text = out if isinstance(out, str) else "\n".join(out)
    payload = text.split("\n", 1)[1] if text.startswith("[") else text
    assert "alpha" in payload and "  indented line" in payload
    assert "    1  " not in text, "raw must carry no line numbers"

    out2 = wq.run_queries(
        [{"read": "doc.md", "lines": "3-4", "raw": True}], cwd=tmp_path)
    t2 = out2 if isinstance(out2, str) else "\n".join(out2)
    assert "alpha\n  indented line" in t2
    assert "3  alpha" not in t2

    out3 = wq.run_queries(
        [{"read": "doc.md", "sections": ["Sec"], "raw": True}],
        cwd=tmp_path)
    t3 = out3 if isinstance(out3, str) else "\n".join(out3)
    assert "beta" in t3
    assert "──" not in t3, "raw must carry no section banner"

    # ...and the decorated default is unchanged.
    out4 = wq.run_queries([{"read": "doc.md", "lines": "3-3"}], cwd=tmp_path)
    t4 = out4 if isinstance(out4, str) else "\n".join(out4)
    assert "3  alpha" in t4


def test_an_oversize_whole_read_is_refused_with_the_map(tmp_path):
    """2026-08-18 owner call: a whole-file read that cannot fit one
    reply is refused with the way in, never silently clipped — 84% of
    the slice's 1,011 truncations were whole reads of the four big
    framework documents, and a 12KB prefix reads exactly like the
    whole file to an agent that does not scroll to the last line."""
    body = "# Big\n" + "\n".join(
        f"## Sec{i}\n" + ("x" * 80 + "\n") * 5 for i in range(6))
    (tmp_path / "big.md").write_text(body, encoding="utf-8")

    out = wq.run_queries([{"read": "big.md"}], cwd=tmp_path,
                         per_query_chars=800)
    assert "could only ever deliver a silent prefix" in out
    assert "truncated at" not in out, "refusal replaces the clip"
    assert "Sec" in out or "outline" in out, "the map rides the refusal"

    # Precise asks still work, clipping semantics intact.
    out2 = wq.run_queries([{"read": "big.md", "sections": ["Sec1"]}],
                          cwd=tmp_path, per_query_chars=800)
    assert "could only ever deliver" not in out2
    out3 = wq.run_queries([{"read": "big.md", "lines": "1-3"}],
                          cwd=tmp_path, per_query_chars=800)
    assert "# Big" in out3

    # Small whole reads are untouched.
    (tmp_path / "small.md").write_text("# S\nhello\n", encoding="utf-8")
    out4 = wq.run_queries([{"read": "small.md"}], cwd=tmp_path,
                          per_query_chars=800)
    assert "hello" in out4


def test_an_oversize_headingless_read_teaches_lines_and_grep(tmp_path):
    (tmp_path / "big.lean").write_text(
        ("-- x\n" + "x" * 60 + "\n") * 40, encoding="utf-8")
    out = wq.run_queries([{"read": "big.lean"}], cwd=tmp_path,
                         per_query_chars=500)
    assert "could only ever deliver a silent prefix" in out
    assert "lines" in out and "grep" in out


def test_raw_read_is_exact_bytes_or_refused_never_truncated(tmp_path):
    """The 2026-08-19 sequel to the 57-entry cluster: a 14KB proposal
    was overwritten with a 992-byte truncated fragment because the raw
    answer still carried the `[n]` label and a silent budget clip. Raw
    is now byte-faithful (no label at all) or REFUSED whole — and it
    must travel alone, so labels never re-enter the round-trip."""
    body = "alpha\nbeta\n"
    (tmp_path / "doc.md").write_text(body, encoding="utf-8")
    out = wq.run_queries([{"read": "doc.md", "raw": True}], cwd=tmp_path)
    assert out == body.rstrip("\n"), "sole raw read is the bytes, unlabelled"

    big = "x" * 300 + "\n"
    (tmp_path / "big.md").write_text(big * 10, encoding="utf-8")
    out2 = wq.run_queries([{"read": "big.md", "raw": True}],
                          cwd=tmp_path, per_query_chars=500)
    assert "raw never truncates" in out2
    assert "xxxx" not in out2, "over-budget raw must not leak a prefix"

    out3 = wq.run_queries([{"read": "doc.md", "raw": True},
                           {"size": "doc.md"}], cwd=tmp_path)
    assert "must be the only query" in out3

    # a raw miss is a labelled refusal, never something that could be
    # mistaken for content
    out4 = wq.run_queries([{"read": "nope.md", "raw": True}], cwd=tmp_path)
    assert out4.startswith("[1]") and "no file" in out4


def test_sections_accept_outline_spelling_and_dynamic_suffixes(tmp_path):
    """40+ self-reports: the outline prints `## Programme (rev 3)` but
    `sections` demanded the bare exact text — copy-pasting from the
    outline (the obvious workflow) failed, and a rev-suffixed heading
    was unnameable in advance. Markers are stripped; the parenthetical
    suffix is presentation on the same name (matched WITH disclosure);
    a true near-miss still refuses, now naming the closest headings."""
    (tmp_path / "doc.md").write_text(
        "## Programme (rev 3, judge-passed)\npayload\n\n"
        "## Pre-search\nother\n", encoding="utf-8")
    out = wq.run_queries([{"read": "doc.md",
                           "sections": ["## Programme (rev 3, judge-passed)"]}],
                         cwd=tmp_path)
    assert "payload" in out, "outline spelling (with ##) must resolve"

    out2 = wq.run_queries([{"read": "doc.md", "sections": ["Programme"]}],
                          cwd=tmp_path)
    assert "payload" in out2 and "[matched" in out2

    out3 = wq.run_queries([{"read": "doc.md",
                            "sections": ["Programme (rev 2)"]}],
                          cwd=tmp_path)
    assert "payload" in out3, "a stale rev suffix still names the section"

    out4 = wq.run_queries([{"read": "doc.md", "sections": ["Programm"]}],
                          cwd=tmp_path)
    assert "no section named" in out4, "a near-miss still refuses (no fuzzy)"

    out5 = wq.run_queries([{"read": "doc.md", "sections": ["search"]}],
                          cwd=tmp_path)
    assert "no section named" in out5 and "close:" in out5
    assert "Pre-search" in out5, "the miss names its nearest heading"


def test_empty_section_says_so(tmp_path):
    """2026-08-22 strategist self-report: a named section that exists
    but is empty answered with silence, indistinguishable from absent,
    misspelled, or truncated."""
    (tmp_path / "doc.md").write_text("## Done\n\n## Next\ncontent\n",
                                     encoding="utf-8")
    out = wq.run_queries([{"read": "doc.md", "sections": ["Done"]}],
                         cwd=tmp_path)
    assert "this section is empty" in out


def test_decl_signature_keeps_line_structure(tmp_path, monkeypatch):
    """2026-08-20 adversary: a `let`-chain flattened to one line is
    "not merely ugly but actively falsifying" — a phantom defect burned
    a worker, a batch and a review round. The decl answer now preserves
    the source's own lines."""
    from Tooling.agent import context as ctx
    (tmp_path / "L_x.lean").write_text(
        "theorem multi_line_sig {n : Nat}\n"
        "    (h : 0 < n) :\n"
        "    n ≤ n * n := by\n  nlinarith\n", encoding="utf-8")
    sig = ctx.goal_display_signature(
        tmp_path, "multi_line_sig", "L_x.lean", "n ≤ n * n", flatten=False)
    assert "\n" in sig, "flatten=False must keep the source's lines"
    flat = ctx.goal_display_signature(
        tmp_path, "multi_line_sig", "L_x.lean", "n ≤ n * n")
    assert "\n" not in flat, "default stays one-line for list surfaces"


def test_explicit_lake_path_overrides_the_skip_list(tmp_path):
    """Agents grepping Mathlib source for a renamed lemma's current
    name hit "nothing to search" on five path spellings and degraded
    into loogle-guessing spirals (both fleets, 2026-08-22). Owner
    ruling: a walk whose root the agent explicitly aimed inside
    `.lake/packages/` is deliberate — grant it; default walks and
    build artifacts stay walled."""
    src = tmp_path / ".lake" / "packages" / "mathlib" / "Mathlib"
    src.mkdir(parents=True)
    (src / "Card.lean").write_text(
        "theorem ncard_le_ncard (h : s \u2286 t) : s.ncard \u2264 t.ncard := hx\n",
        encoding="utf-8")
    build = tmp_path / ".lake" / "build"
    build.mkdir(parents=True)
    (build / "junk.lean").write_text("theorem ncard_le_ncard_junk : x\n",
                                     encoding="utf-8")

    out = wq.run_queries([{"grep": "ncard_le", "in":
                           ".lake/packages/mathlib/Mathlib"}], cwd=tmp_path)
    assert "ncard_le_ncard" in out, "explicit source path must search"

    out2 = wq.run_queries([{"grep": "ncard_le", "in": ".lake/build"}],
                          cwd=tmp_path)
    assert "only under .lake/packages" in out2, "build stays walled"

    out3 = wq.run_queries([{"grep": "ncard_le", "in": "."}], cwd=tmp_path)
    assert "ncard_le_ncard" not in out3, "default walks still skip .lake"

    out4 = wq.run_queries([{"find": "*.lean", "in":
                            ".lake/packages/mathlib/Mathlib"}],
                          cwd=tmp_path)
    assert "Card.lean" in out4


def test_a_multi_level_glob_expands_instead_of_dying_silently(tmp_path):
    """Only the LAST component used to be treated as a pattern, so
    `Library/**/*.lean` walked into a literal `**` directory, matched
    nothing, and the miss note redirected to an unrelated file — the
    presearch seat read that as "the Library is unavailable" and
    shipped an empty block every node (2026-08-22 feedback cluster)."""
    lib = tmp_path / "Library" / "Deep" / "Deeper"
    lib.mkdir(parents=True)
    (lib / "hit.lean").write_text("theorem deep_hit : True := trivial\n",
                                  encoding="utf-8")
    (tmp_path / "Library" / "top.lean").write_text(
        "theorem top_hit : True := trivial\n", encoding="utf-8")

    out = wq.run_queries(
        [{"grep": "theorem", "in": str(tmp_path / "Library" / "**" / "*.lean")}],
        cwd=tmp_path)
    assert "deep_hit" in out and "top_hit" in out

    out2 = wq.run_queries([{"grep": "theorem", "in": "Library/**/*.lean"}],
                          cwd=tmp_path)
    assert "deep_hit" in out2

    # `**` walks still honour the skip list — no silent `.git` sweep.
    git = tmp_path / ".git" / "sub"
    git.mkdir(parents=True)
    (git / "junk.lean").write_text("theorem git_junk : True := trivial\n",
                                   encoding="utf-8")
    out3 = wq.run_queries([{"grep": "theorem", "in": "**/*.lean"}],
                          cwd=tmp_path)
    assert "deep_hit" in out3 and "git_junk" not in out3


def test_a_capped_grep_names_a_resume_handle_and_it_works(tmp_path):
    """The truncation note said only "narrow", which names no reachable
    action when the query is already narrow (2026-08-22 cluster). The
    note must carry an `after` anchor, and resending with it must
    continue with no overlap."""
    f = tmp_path / "big.lean"
    f.write_text("".join(f"theorem t{n} : True := trivial\n"
                         for n in range(20)), encoding="utf-8")
    out = wq.run_queries([{"grep": "theorem", "in": "big.lean", "max": 5}],
                         cwd=tmp_path)
    assert 'after: "' in out, "capped grep must name the resume handle"
    import re as _re
    anchor = _re.search(r'after: "([^"]+)"', out).group(1)
    out2 = wq.run_queries([{"grep": "theorem", "in": "big.lean", "max": 5,
                            "after": anchor}], cwd=tmp_path)
    assert "t5 " in out2 or "t5 :" in out2
    assert "t4 " not in out2 and "t0 " not in out2, "no overlap"

    out3 = wq.run_queries([{"grep": "theorem", "in": "big.lean",
                            "after": "elsewhere.lean:3"}], cwd=tmp_path)
    assert "outside this search" in out3, "a bad anchor teaches the way out"


def test_grep_scan_budget_stops_early_and_names_the_way_out(
    tmp_path, monkeypatch,
) -> None:
    """The old shape read EVERY file before truncating output — one
    broad grep held a CPU for 28 minutes (2026-08-23). The scan stops
    at the budget with partial hits, an `after` handle, and the
    narrow-`in` teaching."""
    for n in range(6):
        (tmp_path / f"f{n}.lean").write_text(
            f"theorem t{n} : True := trivial\n", encoding="utf-8")
    monkeypatch.setattr(wq, "_SCAN_MAX_FILES", 2)
    out = wq.run_queries([{"grep": "theorem", "in": "."}], cwd=tmp_path)
    assert "scan budget hit (2 files)" in out
    assert 'after: "' in out and "narrow `in`" in out


def test_a_broad_walk_prunes_heavy_dirs_unless_aimed_inside(
    tmp_path,
) -> None:
    """`.attempts` / `Papers` / `_spike` are trees a broad grep almost
    never means — the 2026-08-23 stall's walk wandered into them. An
    explicit aim inside one still works."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.lean").write_text(
        "theorem src_hit : True := trivial\n", encoding="utf-8")
    heavy = tmp_path / "Papers" / "deep"
    heavy.mkdir(parents=True)
    (heavy / "p.lean").write_text(
        "theorem paper_hit : True := trivial\n", encoding="utf-8")
    out = wq.run_queries([{"grep": "theorem", "in": "."}], cwd=tmp_path)
    assert "src_hit" in out and "paper_hit" not in out
    out2 = wq.run_queries([{"grep": "theorem", "in": "Papers"}],
                          cwd=tmp_path)
    assert "paper_hit" in out2


def test_write_round_trip_is_byte_faithful_for_lean_notation(spawn):
    """Silent-corruption probe (owner-ordered 2026-08-24): one field
    report claimed the write path dropped Lean's `\` (set difference),
    turning `A \ S` into `A  S` with no error. Pin the framework's own
    chain byte-faithful — backslashes, doubled backslashes, unicode —
    so if the corruption recurs the culprit is provably upstream (model
    or transport), not this path."""
    cwd, mine, theirs = spawn
    bs = chr(92)  # one real backslash, spelled unambiguously
    content = ("theorem fiber_diff (A S : Finset ℕ) :\n"
               f"    (A {bs} S).card ≤ A.card := by\n"
               f"  -- {bs * 2} doubled must survive too\n"
               "  exact Finset.card_le_card (Finset.sdiff_subset)\n")
    out = wq.run_write("new_fiber.lean", content)
    assert out.startswith("wrote")
    on_disk = (mine / "new_fiber.lean").read_text(encoding="utf-8")
    assert on_disk == content
    assert f"A {bs} S" in on_disk and bs * 2 in on_disk


def test_decl_follows_the_wrapper_shape_to_the_strategy_file(
    ws: Path, here: Path,
) -> None:
    """Second alias shape (~29 reports): a proved goal's file can be a
    `def slug := @…sNNN` wrapper with NO alias_target_id marker. The
    framework knows the target sits beside it as _strategy_sNNN.lean —
    follow the pointer, disclosed, instead of shipping the bare pointer
    line the reader must chase by hand."""
    _seed_decl(ws, here, slug="wrapped_goal", sig_lines=1)
    (here / "proofs" / "L_wrapped_goal.lean").write_text(
        "import Mathlib\n"
        "def wrapped_goal : True := @Problems.union_closed.s123\n",
        encoding="utf-8")
    (here / "proofs" / "_strategy_s123.lean").write_text(
        "import Mathlib\n-- strategy scratch\n"
        "theorem s123 : True := trivial\n", encoding="utf-8")
    out = wq.run_queries([{"decl": "wrapped_goal"}], cwd=here)
    assert "wrapper of @s123" in out
    assert "theorem s123 : True := trivial" in out
    assert "_strategy_s123.lean" in out
