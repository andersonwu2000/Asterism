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


def test_a_wrong_section_name_points_at_outline(tmp_path: Path) -> None:
    """No fuzzy matching. A near-miss answered with the wrong section is
    worse than a refusal. And no roster (owner ruling 2026-08-15):
    `outline` already IS the roster with line ranges and sizes, while
    an inlined listing scaled with the file — a 12KB refusal on the
    383-section CATALOG.md. The refusal carries the count and the
    action, nothing that grows."""
    cwd = _workspace(tmp_path)
    out = wq.run_queries(
        [{"read": "Context.md", "sections": ["Programm"]}], cwd=cwd)
    assert "no section named 'Programm'" in out
    assert "sections" in out and "outline" in out
    assert "'Recent decisions'" not in out, "the roster is outline's job"


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
    # `lines` is a deliberate window, so the clip path still applies
    # there; a bare whole read of an oversize file is refused with the
    # map instead (2026-08-18, tested in test_workspace_query).
    out = wq.run_queries([{"read": "big.md", "lines": "1-"}], cwd=cwd,
                         per_query_chars=2000)
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


def test_no_tool_advertises_an_output_schema() -> None:
    """A `-> str` tool with an output schema makes FastMCP emit the SAME
    payload in both `content` and `structuredContent` — so `inspect`'s
    delivery budget governed half the bytes actually sent, and the codex
    exec channel amputated the middle of the rest with no notice. The
    fix was one kwarg and had no test; an independent verifier reverted
    all six decorators and the suite stayed green (2026-08-16).

    EVERY server, not the one the complaint named: the first fix covered
    `knowledge/mcp_tools` and an acceptance pass (2026-08-17) found the
    LSP gateway's five tools — `validate_file` and `errors_at` among
    them, the largest payloads in the system — still doubling."""
    import asyncio
    from Tooling.knowledge import mcp_tools
    from Tooling.lsp import gateway

    for server in (mcp_tools.mcp, gateway.mcp):
        async def _schemas():
            return [(t.name, getattr(t, "outputSchema", None))
                    for t in await server.list_tools()]

        tools = asyncio.run(_schemas())
        assert tools, f"server {server.name!r} advertised no tools at all"
        offenders = [n for n, s in tools if s]
        assert not offenders, (
            f"these {server.name!r} tools still duplicate their payload "
            f"into structuredContent: {offenders}")


def test_every_tool_decorator_in_the_repo_opts_out_of_structured_output() -> None:
    """The source-level twin of the schema check above, for the server
    that does not exist yet: the runtime check names its servers, so a
    THIRD FastMCP server would ship with the same doubling and no test.
    Scans every module under Tooling/ for `@<x>.tool(...)` decorators
    and requires the literal `structured_output=False` on each."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "Tooling"
    offenders = []
    for path in root.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        if ".tool(" not in src:
            continue
        for node in ast.walk(ast.parse(src)):
            for dec in getattr(node, "decorator_list", ()):
                if not (isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr == "tool"):
                    continue
                ok = any(kw.arg == "structured_output"
                         and isinstance(kw.value, ast.Constant)
                         and kw.value.value is False
                         for kw in dec.keywords)
                if not ok:
                    offenders.append(f"{path.relative_to(root.parent)}:"
                                     f"{dec.lineno}")
    assert not offenders, (
        "tool decorators without structured_output=False — each doubles "
        "its payload into structuredContent:\n  " + "\n  ".join(offenders))
