"""`inspect` reads a document by its sections, and a batch is free.

Two defects, one shape: the tool asked for a batch and then priced it
per call, and it returned 40 numbered lines when asked to read a file.
Both taught the agent to send one small question at a time. Measured on
the 2026-08-15 codex probe of Test.provider_probe:

    51 inspect calls, 24 of them carrying exactly ONE query
    24 of the 51 answers came back truncated (results pinned at the cap)
    Context.md read 22 times across 6 sessions — a 3-4 call ladder each
    half of the run's 101 turns were inspect round trips, at ~4,273
      fresh tokens per turn

The section is the right unit because the framework WRITES these
documents: their headings are a stable API, not a guess. Sizing came
from the same measurement — across the 1,459 framework documents agents
read, the largest single section is 9.5KB and the p90 is 2.4KB, which
is what 12KB per query is built to hold.
"""
from __future__ import annotations

from pathlib import Path

from Tooling.knowledge import workspace_query as wq

DOC = """\
# Context

intro line

## Programme

programme body
programme body 2

### Roadmap

roadmap body

## Recent decisions

decision body

## Facts

facts body
"""


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / "Problems").mkdir()
    (tmp_path / "Tooling").mkdir()
    cwd = tmp_path / "Problems" / "Test" / "p"
    cwd.mkdir(parents=True)
    (cwd / "Context.md").write_text(DOC, encoding="utf-8")
    return cwd


def test_a_named_section_arrives_whole_with_its_subsections(
    tmp_path: Path,
) -> None:
    """`## Programme` owns the `### Roadmap` under it — that nesting is
    what a reader means by naming a section, and splitting it would put
    the ladder back one level down."""
    cwd = _workspace(tmp_path)
    out = wq.run_queries(
        [{"read": "Context.md", "sections": ["Programme"]}], cwd=cwd)
    assert "programme body" in out
    assert "roadmap body" in out, "the subsection is part of the section"
    assert "decision body" not in out, "it stopped at the next `##`"
    assert "intro line" not in out


def test_several_sections_come_back_in_one_answer(tmp_path: Path) -> None:
    cwd = _workspace(tmp_path)
    out = wq.run_queries(
        [{"read": "Context.md",
          "sections": ["Programme", "Facts"]}], cwd=cwd)
    assert "programme body" in out and "facts body" in out
    assert "decision body" not in out


def test_a_wrong_section_name_lists_the_real_ones(tmp_path: Path) -> None:
    """No fuzzy matching. A near-miss answered with the wrong section is
    worse than a refusal, and a refusal that does not name the choices
    costs the round trip it was trying to save."""
    cwd = _workspace(tmp_path)
    out = wq.run_queries(
        [{"read": "Context.md", "sections": ["Programm"]}], cwd=cwd)
    assert "no section named" in out
    assert "'Programme'" in out and "'Recent decisions'" in out


def test_outline_is_a_map_not_the_content(tmp_path: Path) -> None:
    cwd = _workspace(tmp_path)
    out = wq.run_queries(
        [{"read": "Context.md", "outline": True}], cwd=cwd)
    assert "Programme" in out and "Recent decisions" in out
    assert "programme body" not in out, "an outline is not the text"
    assert "lines " in out and "chars" in out
    assert "sections" in out, "it must say how to ask for one"


def test_outline_of_a_file_with_no_headings_says_so(tmp_path: Path) -> None:
    cwd = _workspace(tmp_path)
    (cwd / "patch.lean").write_text("theorem t : True := trivial\n" * 5,
                                    encoding="utf-8")
    out = wq.run_queries([{"read": "patch.lean", "outline": True}], cwd=cwd)
    assert "no markdown headings" in out
    assert "lines" in out, "it points at the fallback that does work"


def test_read_without_a_selector_returns_the_whole_file(
    tmp_path: Path,
) -> None:
    """The old default was 40 numbered lines, which is what turned one
    Context.md into a four-call ladder."""
    cwd = _workspace(tmp_path)
    long = "\n".join(f"line {i}" for i in range(1, 121)) + "\n"
    (cwd / "flat.md").write_text(long, encoding="utf-8")
    out = wq.run_queries([{"read": "flat.md"}], cwd=cwd)
    assert "line 1" in out and "line 120" in out


def test_a_batch_does_not_shrink_its_own_answers(tmp_path: Path) -> None:
    """THE PRICING BUG. The budget was `8000 // len(queries)`, so asking
    a second question shrank the answer to the first — the tool asked
    for batches and charged for them, and agents answered by sending one
    query per call (24 of 51 on the probe run)."""
    cwd = _workspace(tmp_path)
    body = "\n".join(f"line {i}" for i in range(1, 400)) + "\n"
    for name in ("a.md", "b.md", "c.md"):
        (cwd / name).write_text(body, encoding="utf-8")

    alone = wq.run_queries([{"read": "a.md"}], cwd=cwd)
    batched = wq.run_queries(
        [{"read": "a.md"}, {"read": "b.md"}, {"read": "c.md"}], cwd=cwd)

    first_alone = alone.split("[1] read")[1]
    first_batched = batched.split("[1] read")[1].split("[2] read")[0]
    assert len(first_batched) >= len(first_alone) - 20, (
        "asking two more questions cost the first answer its content")
    assert "line 399" in first_batched


def test_the_call_limit_defers_whole_queries_by_name(tmp_path: Path) -> None:
    """A COUNT, not a byte pool: the queries that do not fit are named
    and can be re-sent verbatim. A byte pool has to cut into answers
    that were already computed, and the reader cannot tell which."""
    cwd = _workspace(tmp_path)
    (cwd / "x.md").write_text("hello\n", encoding="utf-8")
    qs = [{"read": "x.md"} for _ in range(25)]
    out = wq.run_queries(qs, cwd=cwd, max_queries=20)
    assert out.count("hello") == 20
    assert "5 queries not answered" in out
    assert "the limit is 20" in out
    assert "second call" in out


def test_a_truncated_read_says_where_to_resume_with_no_overlap(
    tmp_path: Path,
) -> None:
    """The old note said "re-run THIS query alone", which re-sends every
    line the reader already paid for. The numbered output makes the
    continuation exact."""
    cwd = _workspace(tmp_path)
    (cwd / "big.md").write_text(
        "\n".join(f"line {i}" for i in range(1, 2000)) + "\n",
        encoding="utf-8")
    out = wq.run_queries([{"read": "big.md"}], cwd=cwd, per_query_chars=2000)
    assert "truncated" in out
    assert '"lines": "' in out, out[-400:]
    # The resume point is the line after the last one delivered.
    last_shown = max(int(ln[:5]) for ln in out.splitlines()
                     if ln[:5].strip().isdigit())
    assert f'"{last_shown + 1}-"' in out


def test_sections_survive_a_file_that_starts_mid_document(
    tmp_path: Path,
) -> None:
    """A heading at line 1 and a heading at the end are the two places an
    off-by-one lives."""
    cwd = _workspace(tmp_path)
    (cwd / "edge.md").write_text("## First\na\n## Last\nz\n",
                                 encoding="utf-8")
    out = wq.run_queries(
        [{"read": "edge.md", "sections": ["Last"]}], cwd=cwd)
    assert "z" in out and "\n    2  a" not in out
    out2 = wq.run_queries(
        [{"read": "edge.md", "sections": ["First"]}], cwd=cwd)
    assert "a" in out2 and "z" not in out2.split("[1] read")[1]
