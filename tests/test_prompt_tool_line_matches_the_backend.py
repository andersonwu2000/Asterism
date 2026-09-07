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
