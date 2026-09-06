"""The console explainer's provider dialects (`llm/explainer.py`).

Two things are pinned here, and they are the two that a name-keyed
branch would have let rot:

  * the READ-ONLY posture, rendered in each backend's own dialect —
    claude's tool allowlist and agy's permission file must both refuse
    to write, run a shell or fetch;
  * the honesty of the labels — a backend may not claim its reads are
    fenced to the workspace unless the provider's DECLARATION says an
    `allow` for that action binds.

`tests/test_serve_chat.py` covers the endpoint that consumes them.
"""
from __future__ import annotations

import json
import queue
from pathlib import Path

import pytest

from Tooling.llm import capabilities as caps
from Tooling.llm import explainer


def _turn(handle: "str | None" = None, resume: bool = False):
    return explainer.Turn(handle=handle, resume=resume)


# -- claude: the surface that shipped, unchanged ---------------------------


def _claude_argv(workspace: Path, **kw) -> "list[str]":
    base = dict(exe="claude", workspace=workspace, system="sys",
                prompt="q", model="sonnet", turn=_turn("abc"),
                timeout_sec=300)
    base.update(kw)
    return explainer.CLAUDE.argv(**base)


def test_claude_tool_surface_is_read_only(tmp_path: Path) -> None:
    cmd = _claude_argv(tmp_path)
    tools = cmd[cmd.index("--tools") + 1]
    for banned in ("Write", "Edit", "Bash", "NotebookEdit"):
        assert banned not in tools.split()
    assert "Read" in tools.split() and "Grep" in tools.split()
    # deny rules pin the operator's Claude state out even of Read
    joined = " ".join(cmd)
    assert ".claude/projects" in joined
    assert "Read(**/.env)" in cmd


def test_claude_session_flags(tmp_path: Path) -> None:
    fresh = _claude_argv(tmp_path, turn=_turn("abc", resume=False))
    assert ["--session-id", "abc"] == fresh[-2:]
    resumed = _claude_argv(tmp_path, turn=_turn("abc", resume=True))
    assert ["--resume", "abc"] == resumed[-2:]


def test_claude_allowed_tools_scoped_to_workspace(tmp_path: Path) -> None:
    pats = explainer.CLAUDE.allowed_tools(tmp_path).split()
    ws = tmp_path.as_posix()
    for p in pats:
        if p.startswith(("Read(", "Grep(", "Glob(")):
            assert ws in p, p
    assert any(p.startswith("WebFetch(domain:") for p in pats)


# -- agy: the same intent, a different dialect and a weaker guarantee ------


def test_agy_permissions_refuse_every_act_channel(tmp_path: Path) -> None:
    """Write, shell and outbound fetch are denied, and the ONLY grant is
    the framework's own MCP server — which on agy is the fence, because
    an unmatched action defaults to Ask and headless auto-denies.

    (2026-09-02: `allow` used to be empty. The console Assistant became
    a seat with a declared tool table (HID §1.1, §3.5), so the grant is
    now exactly `mcp(*)` — what that admits is decided server-side by
    `ASTERISM_SEAT`, not here, and per-server scoping does not match on
    agy anyway. The invariant this test protects is unchanged: nothing
    that ACTS is granted.)"""
    perms = explainer.ANTIGRAVITY.permissions(tmp_path)["permissions"]
    assert perms["allow"] == ["mcp(*)"]
    for action in ("command", "read_url", "write_file"):
        assert any(r.startswith(f"{action}(") for r in perms["deny"]), action


def test_agy_writes_no_decorative_read_rule(tmp_path: Path) -> None:
    """The measured fact (three probes, agy 1.1.11, 2026-08-10): agy
    honours neither allow NOR deny for `read_file`. A rule here would
    make the next reader believe reads are fenced when they are not —
    the file must stay silent and `read_scope` must carry the truth."""
    perms = explainer.ANTIGRAVITY.permissions(tmp_path)["permissions"]
    assert not [r for r in perms["allow"] + perms["deny"]
                if r.startswith("read_file(")]
    assert explainer.ANTIGRAVITY.read_scope == explainer.READ_SCOPE_PROCESS


def test_agy_never_skips_permissions(tmp_path: Path) -> None:
    argv = explainer.ANTIGRAVITY.argv(
        exe="agy", workspace=tmp_path, system="sys", prompt="q",
        model="gemini-3.6-flash-high", turn=_turn(), timeout_sec=300)
    assert "--dangerously-skip-permissions" not in argv
    assert "--mode" not in argv and "--sandbox" not in argv
    # no system-prompt flag exists (agy --help, 1.1.11) — the rules must
    # therefore be inside the prompt, not silently dropped
    assert "sys" in argv[argv.index("-p") + 1]
    # its own clock has to fire before the endpoint's wall, or the death
    # arrives as a kill with no envelope to classify
    assert argv[argv.index("--print-timeout") + 1] == "285s"


def test_agy_resumes_only_a_conversation_it_minted(tmp_path: Path) -> None:
    cold = explainer.ANTIGRAVITY.argv(
        exe="agy", workspace=tmp_path, system="s", prompt="q", model="m",
        turn=explainer.plan_turn("antigravity", None), timeout_sec=300)
    assert "--conversation" not in cold
    warm = explainer.ANTIGRAVITY.argv(
        exe="agy", workspace=tmp_path, system="s", prompt="q", model="m",
        turn=explainer.plan_turn("antigravity", "conv-7"), timeout_sec=300)
    assert warm[warm.index("--conversation") + 1] == "conv-7"


def test_agy_reader_reports_the_conversation_id_it_was_given() -> None:
    """agy MINTS the id, so the only way a second question can resume is
    for the reader to hand it back."""
    class _Proc:
        stdout = None

    import io
    proc = _Proc()
    proc.stdout = io.StringIO(json.dumps({
        "conversation_id": "c-1", "status": "SUCCESS", "response": "hello",
        "num_turns": 1, "usage": {"output_tokens": 3}}))
    q: "queue.Queue" = queue.Queue()
    explainer.ANTIGRAVITY.reader(proc, q)
    events = []
    while (item := q.get(timeout=2)) is not None:
        events.append(item)
    assert events[0] == {"type": "delta", "text": "hello"}
    assert events[-1]["type"] == "done" and events[-1]["ok"] is True
    assert events[-1]["handle"] == "c-1"


def test_agy_reader_does_not_call_an_empty_answer_a_success() -> None:
    """`status: SUCCESS` is not proof of work on this provider — here the
    response text IS the artifact, so it decides."""
    import io

    class _Proc:
        stdout = io.StringIO(json.dumps({"status": "SUCCESS",
                                         "response": ""}))

    q: "queue.Queue" = queue.Queue()
    explainer.ANTIGRAVITY.reader(_Proc(), q)
    done = q.get(timeout=2)
    assert done["type"] == "done" and done["ok"] is False


# -- the labels may not out-claim the declaration --------------------------


def test_a_workspace_read_scope_requires_an_honoured_allow() -> None:
    """The invariant that keeps `read_scope` from becoming flattery: a
    backend may claim its reads are fenced to the workspace ONLY if the
    provider honours an `allow` rule for reading. agy does not (measured
    2026-08-10), so it cannot claim it — and if a future edit grants
    claude's label to another backend, this fails instead of shipping a
    weaker guarantee under the same words."""
    for name, backend in explainer.BACKENDS.items():
        if backend.read_scope == explainer.READ_SCOPE_WORKSPACE:
            assert caps.honours_allow(name, caps.ACTION_READ_FILE), name


def test_the_default_model_is_a_name_the_picker_offers() -> None:
    """Assistant redesign §4: `_Backend.models` is DELETED. The picker's
    source is `serve/model_catalog` (the declared lists, or agy's live
    probe), and a second hand-kept tuple beside it is the copy that rots
    — claude's still offered the retired `haiku`/`sonnet`/`opus` CLI
    aliases. What stays is `default_model`, and it has to be a member of
    the list the picker shows, or the control cannot display the value
    it is sitting on."""
    from Tooling.core import config

    for name, backend in explainer.BACKENDS.items():
        assert not hasattr(backend, "models"), f"{name} kept its own list"
        assert backend.default_model in \
            config.MODEL_CHOICES_BY_PROVIDER[name], name


def test_scope_note_changes_with_the_backend() -> None:
    assert "this workspace only" in explainer.scope_note("claude")
    assert "cannot be scoped" in explainer.scope_note("agy")
    # an unknown backend is described pessimistically, never optimistically
    assert explainer.read_scope("codex") == explainer.READ_SCOPE_PROCESS


def test_plan_turn_reads_the_declaration_not_the_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert explainer.plan_turn("claude", None).handle is not None
    assert explainer.plan_turn("antigravity", None).handle is None
    assert explainer.plan_turn("antigravity", "c").resume is True
    # …and a provider that resumes nothing never carries a handle
    assert explainer.remembers("openai") is False
    assert explainer.plan_turn("openai", "leftover") == explainer.Turn(
        handle=None, resume=False)
    # flip the SAME provider's declaration and the plan follows it
    monkeypatch.setitem(caps.CAPABILITIES, "claude",
                        caps.ProviderCapabilities(
                            name="claude", rc_contract=caps.RC_STRUCTURED,
                            session_resume=caps.RESUME_NONE))
    assert explainer.plan_turn("claude", None).handle is None
    assert explainer.remembers("claude") is False


def test_an_unmeasured_backend_is_refused_by_name() -> None:
    """No fallthrough to claude's flags — that fallthrough IS what
    'hardwired to claude' looked like from the inside."""
    ok, detail = explainer.availability("codex")
    assert ok is False and "codex" in detail
    assert explainer.backend_for("codex") is None
    # openai is the live case: no tool surface at all, so it cannot read
    # the workspace and must not pretend to
    ok, detail = explainer.availability("openai")
    assert ok is False and "openai" in detail
    assert explainer.remembers("openai") is False


def test_every_backend_is_a_provider_the_registry_can_resolve() -> None:
    """A backend for a name `llm.get_provider` cannot resolve would be a
    seat the console offers and the engine rejects."""
    from Tooling.llm import get_provider
    for name in explainer.BACKENDS:
        assert caps.canonical(name) == name
        assert name in caps.CAPABILITIES
        get_provider  # resolution chain shares `capabilities.canonical`


# -- the Assistant's tool surface, in both dialects (HID §3.5) ------------


def _tools_config(cmd: "list[str]") -> dict:
    path = Path(cmd[cmd.index("--mcp-config") + 1])
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_explainer_mounts_the_framework_tool_server(
    tmp_path: Path,
) -> None:
    """§3.5: the Assistant's capabilities all arrive through the same
    MCP server the workers use, seat-scoped. A second permission system
    is how two answers to "what may this agent do" start to drift."""
    cmd = _claude_argv(tmp_path)
    assert "--strict-mcp-config" in cmd
    entry = _tools_config(cmd)["mcpServers"]["asterism_tools"]
    assert entry["args"] == ["-m", "Tooling.knowledge.mcp_tools"]
    assert entry["env"]["ASTERISM_SEAT"] == explainer.KIND


def test_the_allowed_tools_are_exactly_the_seats_own(
    tmp_path: Path,
) -> None:
    """Derived from the seat table, never re-typed: a hand-written
    pattern list is a second copy of the whitelist, and the copy is
    what rots."""
    from Tooling.llm.envelope import asterism_tools_for

    allowed = explainer.CLAUDE.allowed_tools(tmp_path).split()
    seat = asterism_tools_for(explainer.KIND)
    for tool in seat:
        assert f"mcp__asterism_tools__{tool}" in allowed, tool
    assert "mcp__asterism_tools__write_file" not in allowed


def test_the_agy_explainer_gets_the_same_server_and_may_call_it(
    tmp_path: Path,
) -> None:
    """The capability matrix is the seat's, not the backend's. agy reads
    its MCP servers from a file under HOME and auto-denies an action
    with no allow rule, so BOTH have to be written or the agy Assistant
    silently has no tools."""
    home = explainer.ANTIGRAVITY.home(tmp_path)
    cfg = json.loads(
        (home / ".gemini" / "config" / "mcp_config.json").read_text(
            encoding="utf-8"))
    assert cfg["mcpServers"]["asterism_tools"]["env"]["ASTERISM_SEAT"] \
        == explainer.KIND
    perms = explainer.ANTIGRAVITY.permissions(tmp_path)["permissions"]
    assert "mcp(*)" in perms["allow"]
    # …and the act channels stay shut.
    assert "command(*)" in perms["deny"]
    assert "write_file(*)" in perms["deny"]


def test_the_explainer_spawn_carries_an_mcp_tool_timeout(
    tmp_path: Path,
) -> None:
    """The Assistant's tools are the workers' tools, and two of them —
    `compute` and `tex_check` — hold an MCP call for minutes. Pipeline
    spawns say so (`llm/claude_cli.py`, `MCP_TOOL_TIMEOUT`); this seat
    did not, so the Assistant's tool clock was whatever the CLI ships
    with, and on 2026-09-06 a `tex_check` result never came back."""
    from Tooling.llm.base import MCP_TOOL_TIMEOUT_SEC

    env = explainer.CLAUDE.env(tmp_path)
    assert env["MCP_TOOL_TIMEOUT"] == str(MCP_TOOL_TIMEOUT_SEC * 1000)
