"""The tool line a worker reads must be the tools it actually has.

Every NL prompt opens by naming its tools, and that line was written
for claude. A codex worker was handed `Read / Grep / Write / Edit` and
has none of them (`capabilities` DELTA 1: with the shell off it has no
file tool at all), so on 2026-08-12 it spent two turns enumerating
`ALL_TOOLS` to discover what it really had. On 08-15, with the section
reader shipped, it used `read` WHOLE FILE 73 times and `sections` five —
the prompt example it was given showed the old shape.

The fact lives in ONE place (`capabilities.native_file_tools`) and the
prompts render from it. What is pinned here is that the pair of flags
is total: the template renderer is fail-open, so a missing flag keeps
its block, and a spawn that received only one of the two would read
BOTH tool lines and be told two contradictory things about itself.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from Tooling.agent.runtime import render_prompt_template
from Tooling.llm import capabilities as caps

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = [
    ROOT / "Tooling" / "prompts" / "adversary" / "adversary.md",
    ROOT / "Tooling" / "prompts" / "strategist" / "routine.md",
    ROOT / "Tooling" / "prompts" / "strategist" / "inject_batch_done.md",
]


def _tool_lines(path: Path, provider: str) -> list[str]:
    text = render_prompt_template(
        path.read_text(encoding="utf-8"),
        flags=caps.prompt_tool_flags(provider))
    return [ln for ln in text.splitlines() if ln.startswith("Tools:")]


@pytest.mark.parametrize("path", PROMPTS, ids=lambda p: p.name)
@pytest.mark.parametrize("provider",
                         ["claude", "codex", "antigravity", "nonesuch"])
def test_exactly_one_tool_line_reaches_the_worker(path, provider) -> None:
    lines = _tool_lines(path, provider)
    assert len(lines) == 1, (
        f"{path.name} on {provider}: {len(lines)} tool lines — a worker "
        f"reading two of them is being told two different things about "
        f"what it can do")


@pytest.mark.parametrize("path", PROMPTS, ids=lambda p: p.name)
def test_a_backend_with_file_tools_is_told_about_them(path) -> None:
    line = _tool_lines(path, "claude")[0]
    assert "Read" in line and "Grep" in line


@pytest.mark.parametrize("path", PROMPTS, ids=lambda p: p.name)
def test_a_backend_without_them_is_taught_the_section_read(path) -> None:
    """Not "you have no Read" — the tool list IS the statement. What it
    needs instead is the cheap shape: name the section."""
    line = _tool_lines(path, "codex")[0]
    assert "Read" not in line and "Grep" not in line
    assert '"sections"' in line
    assert "outline" in line
    # "ask everything in ONE call" is GONE (owner ruling 2026-08-15): a
    # rule that taxes the follow-up teaches an agent not to dare one it
    # needs. What the line teaches instead is that batching is free and
    # a deferred query is resent, not lost.
    assert "ONE call" not in line
    assert "Batch" in line and "deferred" in line


def test_an_undeclared_backend_gets_the_pessimistic_line() -> None:
    """Promising a tool that is not there is the failure that was
    measured; the reverse costs a worker one redundant sentence."""
    flags = caps.prompt_tool_flags("no-such-backend")
    assert flags == {"native_file_tools": False, "mcp_only_reads": True}


def test_the_flag_pair_is_total() -> None:
    """Fail-open rendering makes a PARTIAL answer worse than none, so
    the helper always returns both names."""
    for provider in ("claude", "codex", "antigravity", "openai"):
        assert set(caps.prompt_tool_flags(provider)) == {
            "native_file_tools", "mcp_only_reads"}
        f = caps.prompt_tool_flags(provider)
        assert f["native_file_tools"] is not f["mcp_only_reads"]


def test_the_declaration_matches_what_each_backend_measured() -> None:
    """claude and agy have file tools; codex does not (its `read`
    answers "NO-READ-TOOL"), and `openai` is a single-shot HTTP call
    with no tools at all."""
    assert caps.capabilities_for("claude").native_file_tools is True
    assert caps.capabilities_for("antigravity").native_file_tools is True
    assert caps.capabilities_for("codex").native_file_tools is False
    assert caps.capabilities_for("openai").native_file_tools is False


def test_the_flags_are_added_by_the_spawn_path_not_by_each_caller(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A pipeline that forgot to pass them would hand its worker a tool
    list written for a different provider — the whole defect. So the
    spawn path adds them for every kind, and a caller's own flags still
    win (a Context block that must render regardless)."""
    from Tooling.agent import runtime
    seen: dict = {}

    class _Provider:
        def spawn(self, req):
            seen.update(req.prompt_flags or {})
            return 0

    monkeypatch.setattr(runtime.llm, "get_provider",
                        lambda kind=None: _Provider())
    monkeypatch.setattr(caps, "provider_for_kind", lambda k, **kw: "codex")
    monkeypatch.setattr(runtime, "_record_spawn_usage",
                        lambda **kw: None)
    monkeypatch.setattr(runtime, "_artifact_audit", lambda **kw: None)

    runtime.spawn_llm(kind="strategist", prompt_path=tmp_path / "p.md",
                      problem_dir=tmp_path, attempts_dir=tmp_path,
                      prompt_flags={"has_history": True})

    assert seen["mcp_only_reads"] is True
    assert seen["native_file_tools"] is False
    assert seen["has_history"] is True, "the caller's own flags survive"


def test_every_adapter_hands_the_flags_to_the_renderer() -> None:
    """And the spawn path adding them is only half of it: the ADAPTER
    has to pass them on. `render_prompt_template` is fail-open, so an
    adapter that drops `flags` renders every conditional block — both
    halves of the theory reviewer's criterion 3, every not-yet-
    applicable strategist paragraph — and the same prompt then means
    different things depending on which backend the seat sits on.

    Read off the source rather than by spawning four real providers:
    the claim is about the call site, and three of the four adapters
    need a CLI on the machine to reach it."""
    import ast
    import inspect
    from Tooling.llm import antigravity_cli, claude_cli, codex_cli
    from Tooling.llm import openai_api

    # codex composes its stdin payload out of claude_cli's two helpers,
    # so its call site IS `claude_cli._load_prompt` — named here so a
    # future split of that seam fails this test rather than the fleet.
    assert "_load_prompt" in inspect.getsource(
        codex_cli.CodexCliProvider.spawn)

    for mod in (claude_cli, antigravity_cli, openai_api):
        tree = ast.parse(inspect.getsource(mod))
        calls = [n for n in ast.walk(tree)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "id", "") == "render_prompt_template"]
        assert calls, f"{mod.__name__} renders no prompt template"
        for call in calls:
            names = {kw.arg for kw in call.keywords}
            assert "flags" in names, (
                f"{mod.__name__}:{call.lineno} calls "
                f"render_prompt_template without `flags` — the renderer "
                f"is fail-open, so every conditional block would render")


# ---------------------------------------------------------------------
# `feedback(note, evidence)` is advertised in DEVELOPER MODE ONLY
# ---------------------------------------------------------------------
#
# Owner amendment 2026-09-07. The tool stays registered on every seat
# (its ack already says "this workspace does not collect framework
# feedback" when the sink is off), but an end user's agents must not
# spend attention on a channel that reports to the framework's
# developer. So the sentence lives in a `feedback_tool` block and the
# flag comes from the SAME switch that decides whether the sink
# collects — `pipeline._feedback.feedback_enabled`.

_FEEDBACK_SENTENCE = "`feedback(note, evidence)` —"

#: Every prompt carrying the block. Enumerated from disk rather than
#: typed: a seat prompt added with the block and forgotten here would
#: otherwise be tested by nothing.
_FEEDBACK_PROMPTS = sorted(
    p for p in (ROOT / "Tooling" / "prompts").rglob("*.md")
    if "<!-- #if feedback_tool -->" in p.read_text(encoding="utf-8"))


def test_the_block_reaches_every_seat_prompt() -> None:
    """The seats that filed nothing under the retired survivor leg —
    presearch, the librarian family, the intake turn — are exactly the
    ones that had no channel. Adding the tool without telling them
    would have reproduced that silence."""
    names = {p.name for p in _FEEDBACK_PROMPTS}
    assert {"adversary.md", "routine.md", "inject_batch_done.md",
            "theory.md", "review.md", "formalize.md", "mint.md",
            "intake.md", "presearch.md", "classify.md",
            "migrate.md"} <= names, sorted(names)


@pytest.mark.parametrize("path", _FEEDBACK_PROMPTS, ids=lambda p: p.name)
def test_outside_developer_mode_no_prompt_names_the_tool(path) -> None:
    rendered = render_prompt_template(
        path.read_text(encoding="utf-8"),
        flags={**caps.prompt_tool_flags("claude"), "feedback_tool": False})
    assert _FEEDBACK_SENTENCE not in rendered
    assert "#if feedback_tool" not in rendered      # marker stripped too


@pytest.mark.parametrize("path", _FEEDBACK_PROMPTS, ids=lambda p: p.name)
@pytest.mark.parametrize("provider", ["claude", "codex"])
def test_in_developer_mode_both_tool_line_variants_carry_it(
    path, provider,
) -> None:
    """Once, in either variant — the native-file-tools line and the
    mcp-only-reads line are alternatives, and a sentence duplicated
    across them would reach a worker twice."""
    rendered = render_prompt_template(
        path.read_text(encoding="utf-8"),
        flags={**caps.prompt_tool_flags(provider), "feedback_tool": True})
    assert rendered.count(_FEEDBACK_SENTENCE) == 1


def test_the_flag_comes_from_the_one_gate_the_sink_uses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A second switch would let the prompts advertise a channel that
    files nothing, or hide one that collects."""
    from Tooling.agent import runtime
    seen: dict = {}

    class _Provider:
        def spawn(self, req):
            seen.update(req.prompt_flags or {})
            return 0

    monkeypatch.setattr(runtime.llm, "get_provider",
                        lambda kind=None: _Provider())
    monkeypatch.setattr(caps, "provider_for_kind", lambda k, **kw: "codex")
    monkeypatch.setattr(runtime, "_record_spawn_usage", lambda **kw: None)
    monkeypatch.setattr(runtime, "_artifact_audit", lambda **kw: None)
    attempts = tmp_path / ".attempts" / "pid"
    attempts.mkdir(parents=True)

    for value, expected in (("false", False), ("true", True)):
        monkeypatch.setenv("ASTERISM_FEEDBACK_ENABLED", value)
        runtime.spawn_llm(kind="strategist", prompt_path=tmp_path / "p.md",
                          problem_dir=tmp_path, attempts_dir=attempts)
        assert seen["feedback_tool"] is expected


def test_the_flag_is_passed_explicitly_even_when_it_is_false(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The renderer is fail-OPEN: an omitted flag KEEPS its block, so
    "we only pass it when it is on" would advertise the tool in exactly
    the installations the gate exists to hide it from."""
    from Tooling.agent import runtime
    seen: dict = {}

    class _Provider:
        def spawn(self, req):
            seen.update({"flags": dict(req.prompt_flags or {})})
            return 0

    monkeypatch.setattr(runtime.llm, "get_provider",
                        lambda kind=None: _Provider())
    monkeypatch.setattr(caps, "provider_for_kind", lambda k, **kw: "claude")
    monkeypatch.setattr(runtime, "_record_spawn_usage", lambda **kw: None)
    monkeypatch.setattr(runtime, "_artifact_audit", lambda **kw: None)
    monkeypatch.setenv("ASTERISM_FEEDBACK_ENABLED", "false")

    runtime.spawn_llm(kind="adversary", prompt_path=tmp_path / "p.md",
                      problem_dir=tmp_path, attempts_dir=tmp_path,
                      prompt_flags={"more_rounds": True})

    assert "feedback_tool" in seen["flags"]
    assert seen["flags"]["feedback_tool"] is False
    assert seen["flags"]["more_rounds"] is True   # caller's own survive
