"""The framework's tool surface over MCP — the whitelist's new home.

A shell allowlist is only a control where the provider can express one.
claude's matcher takes `<prefix> *`; the Antigravity CLI's takes an exact
literal or `*` and nothing between (measured 2026-07-30), so "loogle only"
was inexpressible there and the run went out with `command(*)`. Within a
day that cost a Strategist wake 32 minutes to an agent-authored `python -c`
loop scanning to 10**15 — a compute channel, where all the design
attention had gone to the write channel.

These tests pin the replacement: one tool list, same for every provider,
with the framework owning the command line.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest


def test_server_exposes_exactly_the_intended_tools() -> None:
    """The tool list IS the whitelist. Adding one is a deliberate act,
    so it fails here first — which is the difference between this and a
    permission file nobody rereads."""
    import asyncio

    from Tooling.knowledge import mcp_tools

    tools = asyncio.run(mcp_tools.mcp.list_tools())
    assert {t.name for t in tools} == {
        "loogle", "validate_json",
        # The shell's replacements (2026-08-10): reading, calculating,
        # and the Scholar's two curated network commands, which had to
        # move here or closing Bash would decapitate that role.
        "inspect", "compute", "paper_search", "paper_fetch",
    }


def test_validate_json_covers_the_most_used_shell_call() -> None:
    """`python -m json.tool` was the single most-used command across the
    07-30 agy legs (~47 of ~104), ahead of loogle — agents check their
    own decision.json parses rather than spend a round on a rejection.
    Denying the shell without replacing this would trade a measured
    behaviour for the theory that the framework's parse error suffices."""
    from Tooling.knowledge import mcp_tools

    assert mcp_tools.validate_json('{"a": 1, "b": 2}') == "OK: 2 top-level key(s)"
    assert mcp_tools.validate_json("[1,2,3]") == "OK: array of 3"
    bad = mcp_tools.validate_json('{"a": }')
    assert bad.startswith("INVALID:") and "line" in bad


def test_loogle_tool_reports_failure_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead network is an answer the agent can act on; an exception
    across the MCP boundary is not."""
    from Tooling.knowledge import loogle as _loogle
    from Tooling.knowledge import mcp_tools

    monkeypatch.setattr(_loogle, "query",
                        lambda *a, **k: (1, "loogle network error: boom"))
    out = mcp_tools.loogle("Nat.succ _")
    assert "unavailable" in out and "boom" in out


def test_loogle_tool_truncates(monkeypatch: pytest.MonkeyPatch) -> None:
    """The agent pays for every byte in its next turn, so the cap is the
    framework's job — it owns the call now, which is the whole point."""
    from Tooling.knowledge import loogle as _loogle
    from Tooling.knowledge import mcp_tools

    monkeypatch.setattr(_loogle, "query",
                        lambda *a, **k: (0, "x" * (mcp_tools.MAX_CHARS * 2)))
    out = mcp_tools.loogle("_")
    assert len(out) < mcp_tools.MAX_CHARS + 200
    assert "truncated" in out


def test_tools_config_is_stdio_with_pythonpath(tmp_path: Path) -> None:
    """PYTHONPATH, not cwd: the client spawns the server from the spawn's
    own directory, and neither claude's nor agy's MCP schema carries a
    cwd field."""
    from Tooling import pipeline

    att = tmp_path / "att"
    att.mkdir()
    path = pipeline.write_tools_mcp_config(att, tmp_path)
    cfg = json.loads(path.read_text(encoding="utf-8"))
    entry = cfg["mcpServers"]["asterism_tools"]
    assert entry["type"] == "stdio"
    assert entry["args"] == ["-m", "Tooling.knowledge.mcp_tools"]
    assert entry["env"]["PYTHONPATH"] == str(tmp_path)
    # No gateway session for a wake with no Lean file open — registering
    # one would hold a backend slot for nothing.
    assert set(cfg["mcpServers"]) == {"asterism_tools"}


def test_gateway_config_carries_the_same_tools_entry() -> None:
    """Both configs must build the entry from one helper. Two copies is
    how the providers drift apart, which is the failure this whole change
    exists to end."""
    from Tooling import pipeline

    src = inspect.getsource(pipeline._write_mcp_config)
    assert "tools_mcp_entry(workspace)" in src
    assert '"asterism_tools"' in src


def test_every_prompt_naming_a_tool_gets_a_config() -> None:
    """Naming a tool in a prompt is a promise the dispatch must keep.

    Caught while landing this change: the librarian and presearch prompts
    were rewritten to call `loogle(...)` while their spawns passed no MCP
    config at all, so the instruction would have named a tool the agent
    could not call — a silent capability gap, the same shape as the
    retired-pipeline vocabulary that told workers about roles that no
    longer existed."""
    repo = Path(__file__).resolve().parents[1]
    prompts = repo / "Tooling" / "prompts"
    # prompt directory -> the module that spawns that kind
    owners = {
        "strategist": ["Tooling/pipeline/strategist.py"],
        "adversary": ["Tooling/pipeline/adversary.py"],
        "librarian": ["Tooling/pipeline/librarian/run.py"],
        "formalizer": ["Tooling/pipeline/_retry.py"],
        "_shared": ["Tooling/pipeline/_presearch.py",
                    "Tooling/pipeline/_retry.py"],
    }
    missing: list[str] = []
    for sub, modules in owners.items():
        names = " ".join(
            p.read_text(encoding="utf-8")
            for p in (prompts / sub).glob("*.md"))
        if "loogle(" not in names and "validate_json(" not in names:
            continue
        if not any("mcp_config_path=" in (repo / m).read_text(encoding="utf-8")
                   for m in modules):
            missing.append(f"{sub} prompts name a tool; none of "
                           f"{modules} passes mcp_config_path")
    assert not missing, "\n  ".join(missing)


def test_no_prompt_names_a_shell_command_the_agent_cannot_run() -> None:
    """The other direction of the pairing, and the one that was missed.

    When `json.tool` left the Bash allowlist the prompts kept telling
    agents to run `python -m json.tool <file>` — four of them. The
    existing pin only checked that a prompt naming an MCP tool gets a
    config; nothing checked that a prompt naming a SHELL command still
    has a shell. Every `python -m X` a prompt names must still be
    granted somewhere in the claude allowlist (scholar's two curated
    network commands are the only survivors)."""
    import re

    repo = Path(__file__).resolve().parents[1]
    src = (repo / "Tooling" / "llm" / "claude_cli.py").read_text(
        encoding="utf-8")
    granted = set(re.findall(r"Bash\(python -m ([\w.]+)", src))

    named: dict[str, str] = {}
    for p in (repo / "Tooling" / "prompts").rglob("*.md"):
        for mod in re.findall(r"python -m ([\w.]+)",
                              p.read_text(encoding="utf-8")):
            named.setdefault(mod, p.name)
    ungranted = {m: f for m, f in named.items() if m not in granted}
    assert not ungranted, (
        "prompts name shell commands no allowlist grants: "
        + ", ".join(f"{m} ({f})" for m, f in sorted(ungranted.items())))


def test_judge_contract_rides_the_projection_not_the_prompt() -> None:
    """17 lines of decision-kind reference were inlined into every judge
    spawn. They are reference, not instruction, so they move to the
    projection — in their own file: `decisions.md` is what the Strategist
    wrote, and a judge that prosecutes attribution should not find
    framework text inside it."""
    import inspect

    from Tooling.pipeline import adversary

    repo = Path(__file__).resolve().parents[1]
    fragment = repo / "Tooling" / "prompts" / "adversary" / "_contract.md"
    prompt = (repo / "Tooling" / "prompts" / "adversary"
              / "adversary.md").read_text(encoding="utf-8")

    assert fragment.exists()
    assert "`Inject` —" in fragment.read_text(encoding="utf-8")
    # Moved, not copied.
    assert "The Strategist's contract (verbatim)" not in prompt
    assert "`contract.md`" in prompt          # the judge is told it exists
    src = inspect.getsource(adversary.build_projection)
    assert '"contract.md"' in src


def test_loogle_left_the_shell_allowlist() -> None:
    """The claude side kept a working Bash rule for months; it is removed
    here not because it failed but because it could not be mirrored on the
    other provider, and a control that only one provider honours is not a
    control."""
    from Tooling.llm import claude_cli

    assert set(claude_cli._TOOLS_MCP_PATTERNS) == {
        "mcp__asterism_tools__loogle",
        "mcp__asterism_tools__validate_json",
    }
    # Empty, so an unmatched Bash call falls to the prompt that headless
    # auto-denies. `json.tool` went with loogle once `validate_json`
    # existed — and not for tidiness: `python -m json.tool <in> <out>`
    # writes its OUTFILE, so the trailing `*` was a write channel that
    # two months of comments called side-effect-free.
    assert claude_cli.DEFAULT_BASH_ALLOWED == ""
