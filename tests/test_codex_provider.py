"""The codex provider, pinned against what was MEASURED on 0.147.0.

Every assertion below stands for a probe that cost real tokens on
2026-08-12, and the comment says which. A future reader flipping one of
these settings "because it looks redundant" is the reason each one
records its evidence rather than just its value.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from Tooling.llm import codex_cli
from Tooling.llm.base import transcript_dest
from Tooling.llm.base import LLMRequest


def _req(tmp_path: Path, **kw) -> LLMRequest:
    att = tmp_path / "att"
    att.mkdir(exist_ok=True)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("do it\n", encoding="utf-8")
    base = dict(kind="formalizer", prompt_path=prompt,
                problem_dir=tmp_path, attempts_dir=att,
                timeout_sec=900, session_id="sid-1")
    base.update(kw)
    return LLMRequest(**base)


# ------------------------------------------------- the capability gate

def test_the_tool_gate_is_features_not_tools(tmp_path: Path) -> None:
    """MEASURED: `[tools]` carries exactly ONE field (`web_search`) and
    cannot remove the shell — `tools.shell` comes back `unknown
    configuration field`. The switches that work are feature flags, and
    with these two off the model's tool list loses `shell_command` and
    every connector the ChatGPT account has (Gmail send/delete, calendar
    writes, site deploys, plugin uninstall).

    `[agents] enabled` is separate and also measured: `--disable
    multi_agent` does NOT remove `multi_agent_v1__*` — only this does,
    and leaving it on lets a worker spawn sub-agents whose spend never
    reaches the framework's ledger."""
    cfg = codex_cli._render_config(_req(tmp_path), "gpt-5.6-luna", "xhigh")
    assert "shell_tool = false" in cfg
    assert "apps = false" in cfg
    assert "[agents]\nenabled = false" in cfg


def test_no_human_is_attached_so_nothing_may_ask(tmp_path: Path) -> None:
    """Headless `exec` has no reviewer: an approval request resolves to
    `user cancelled …`, so anything that can ask must be told not to."""
    cfg = codex_cli._render_config(_req(tmp_path), "m", "xhigh")
    assert 'approval_policy = "never"' in cfg


def test_the_model_and_effort_reach_the_config(tmp_path: Path) -> None:
    cfg = codex_cli._render_config(_req(tmp_path), "gpt-5.6-luna", "xhigh")
    assert "model = 'gpt-5.6-luna'" in cfg
    assert 'model_reasoning_effort = "xhigh"' in cfg


# --------------------------------------------------------------- MCP

def _mcp_config(tmp_path: Path) -> Path:
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": {
        "asterism_tools": {"type": "stdio", "command": "py.exe",
                           "args": ["-m", "Tooling.knowledge.mcp_tools"],
                           "env": {"PYTHONPATH": r"D:\Asterism"}},
        "lsp": {"type": "http", "url": "http://127.0.0.1:8765/mcp",
                "headers": {"X-Asterism-Session": "tok"}},
    }}), encoding="utf-8")
    return path


def test_every_mcp_server_is_pre_approved_and_required(
    tmp_path: Path,
) -> None:
    """Two settings, both load-bearing, both measured.

    `approve`: without it EVERY MCP call comes back `user cancelled MCP
    tool call` — the tool is still listed, so the failure reads like a
    model that would not act rather than a gate. `auto` does not fix it;
    only `approve` does.

    `required`: a server that cannot start fails the spawn instead of
    producing a worker with no tools. claude has no equivalent, and a
    silently tool-less worker is the failure mode this framework has
    paid for more than once."""
    toml = codex_cli._mcp_servers_toml(_mcp_config(tmp_path))
    assert toml.count('default_tools_approval_mode = "approve"') == 2
    assert toml.count("required = true") == 2


def test_both_transport_shapes_survive_the_translation(
    tmp_path: Path,
) -> None:
    toml = codex_cli._mcp_servers_toml(_mcp_config(tmp_path))
    assert "[mcp_servers.asterism_tools]" in toml
    assert "command = 'py.exe'" in toml
    assert "args = ['-m', 'Tooling.knowledge.mcp_tools']" in toml
    assert "[mcp_servers.asterism_tools.env]" in toml
    # The gateway's session token rides an ordinary header; if this
    # stops rendering, every Lean tool call is unauthenticated.
    assert "url = 'http://127.0.0.1:8765/mcp'" in toml
    assert "[mcp_servers.lsp.http_headers]" in toml
    assert "'X-Asterism-Session' = 'tok'" in toml


def test_no_mcp_config_renders_no_servers(tmp_path: Path) -> None:
    assert codex_cli._mcp_servers_toml(None) == ""


# ------------------------------------------------------- TOML dialect

def test_windows_paths_use_literal_strings() -> None:
    """MEASURED: a double-quoted TOML string treats `\\U` in
    `C:\\Users\\…` as an escape and the config dies with `too few
    unicode value digits`. Literal strings have no escapes, so this is
    the only shape a Windows path survives."""
    rendered = codex_cli._toml_str(r"C:\Users\ander\AppData\Local\x")
    assert rendered == r"'C:\Users\ander\AppData\Local\x'"
    assert "\\\\" not in rendered


def test_a_path_that_cannot_be_expressed_fails_loudly() -> None:
    """A single quote would silently truncate the value, and a
    half-written path in a permission fence is worse than no spawn."""
    with pytest.raises(ValueError):
        codex_cli._toml_str("D:/it's/here")


# ------------------------------------------------------- event stream

def test_the_thread_id_is_captured_because_we_cannot_mint_it() -> None:
    """codex mints the id; resume is capture-then-replay. Losing this
    turns every retry into an amnesiac cold start."""
    ev = codex_cli._Events()
    ev.feed_line('{"type":"thread.started","thread_id":"019ff-abc"}')
    assert ev.thread_id == "019ff-abc"


def test_usage_comes_off_turn_completed() -> None:
    ev = codex_cli._Events()
    ev.feed_line('{"type":"turn.completed","usage":{"input_tokens":10,'
                 '"cached_input_tokens":4,"output_tokens":2}}')
    assert ev.turns == 1
    assert ev.usage["input_tokens"] == 10


@pytest.mark.parametrize("line", [
    '{"type":"turn.failed","error":{"message":"model refused"}}',
    '{"type":"error","message":"stream error: broken pipe"}',
])
def test_a_failed_turn_is_visible_even_though_rc_will_be_zero(
    line: str,
) -> None:
    """THE measured hazard: an API 400 ("model is not supported when
    using Codex with a ChatGPT account") exits ZERO. Reading rc=0 as
    "the agent had its fair chance" would charge a goal for the vendor
    rejecting the request, so the outcome has to come off the stream."""
    ev = codex_cli._Events()
    ev.feed_line(line)
    assert ev.failed


def test_an_item_level_error_is_not_a_failed_turn() -> None:
    """`item.type == "error"` is the vendor's non-fatal warning channel
    (a fallback-metadata notice arrives that way). Treating it as a
    failure would fail spawns that went on to succeed."""
    ev = codex_cli._Events()
    ev.feed_line('{"type":"item.completed","item":{"id":"i1",'
                 '"type":"error","message":"metadata not found"}}')
    assert ev.failed is None


def test_junk_lines_never_break_the_reader() -> None:
    ev = codex_cli._Events()
    for junk in ("", "Reading additional input from stdin...", "{oops",
                 "ERROR: not json"):
        ev.feed_line(junk)
    assert ev.thread_id is None and ev.failed is None


# ------------------------------------------------------------- quota

def test_a_healthy_window_states_no_reset() -> None:
    assert codex_cli._note_quota(
        {"primary": {"used_percent": 5.0, "resets_at": 4102444800},
         "rate_limit_reached_type": None}) is False
    assert codex_cli.take_quota_reset() is None


def test_a_spent_window_hands_over_its_reset_once() -> None:
    """Consumed once on purpose: a stale epoch replayed onto a later
    block would park the seat against a window that already reopened."""
    assert codex_cli._note_quota(
        {"primary": {"used_percent": 100.0, "resets_at": 4102444800},
         "rate_limit_reached_type": "primary"}) is True
    assert codex_cli.take_quota_reset() == 4102444800.0
    assert codex_cli.take_quota_reset() is None


def test_rate_limits_are_read_from_the_spawns_own_rollout(
    tmp_path: Path,
) -> None:
    """Per-spawn CODEX_HOME is what makes this exact: the newest rollout
    under it belongs to this spawn and nobody else, so no attribution
    guessing is needed."""
    day = tmp_path / "sessions" / "2026" / "08" / "12"
    day.mkdir(parents=True)
    (day / "rollout-x.jsonl").write_text("\n".join([
        json.dumps({"type": "session_meta", "payload": {"id": "s"}}),
        json.dumps({"type": "event_msg", "payload": {
            "type": "token_count",
            "rate_limits": {"primary": {"used_percent": 4.0},
                            "plan_type": "prolite"}}}),
    ]), encoding="utf-8")
    limits = codex_cli._read_rate_limits(tmp_path)
    assert limits and limits["plan_type"] == "prolite"


def test_no_rollout_is_not_an_error(tmp_path: Path) -> None:
    assert codex_cli._read_rate_limits(tmp_path) is None


def test_the_reset_source_is_chosen_by_declaration_not_by_name() -> None:
    """The dispatcher used to carry `if seat == "antigravity"` inline.
    Every live provider now answers through the declaration, and a
    backend nobody measured gets None rather than a guess.

    claude joined the list on 2026-08-13, and the assertion here used to
    read `is False` on the reasoning that a provider with a usage
    endpoint has no need to state its own reset. That reasoning broke on
    the one day it mattered: the endpoint is exactly what fails when
    every client on the account queries it in the second the window
    dies, and the refusal a spawn already paid for carried `resetsAt`
    the whole time. Having both is not redundancy."""
    from Tooling.core import quota
    from Tooling.llm import capabilities as caps
    for backend in ("codex", "antigravity", "claude"):
        assert caps.capabilities_for(backend).states_quota_reset is True
    # Nothing observed yet ⇒ still None; the source is consume-once.
    assert quota.reset_epoch("claude") is None
    assert quota.reset_epoch("no-such-backend") is None


# ----------------------------------------------------- session memory

def test_the_thread_map_round_trips(tmp_path: Path) -> None:
    att = tmp_path / "att"
    att.mkdir()
    codex_cli._remember_thread(att, "sid-1", "thread-9")
    assert codex_cli._load_session_map(att)["sid-1"] == "thread-9"
    # A second pipeline id in the same dir must not clobber the first —
    # the Strategist's revision rounds share one attempts_dir.
    codex_cli._remember_thread(att, "sid-2", "thread-10")
    both = codex_cli._load_session_map(att)
    assert both == {"sid-1": "thread-9", "sid-2": "thread-10"}


def test_usage_lands_in_the_shape_spawn_usage_reads() -> None:
    """One writer, not two: `_persist_parser_state` already writes this
    file WITH the trap fields the retry helper reads, so the provider
    must not write a usage-only version over the top of it.

    AND IN CLAUDE'S UNITS. `input_tokens` means "the fresh part" to
    every consumer of `spawn_usage`; codex reports the WHOLE prompt
    there with `cached_input_tokens` as a subset of it (measured on the
    08-12 rollout, 28/28 turns: `total == input + output`). Copying both
    across counted the cached prompt twice, so the fresh figure is the
    difference.
    """
    from Tooling.llm.stream_parser import StreamParser
    p = StreamParser(dialect="codex")
    p.feed_line('{"type":"turn.started"}')
    p.feed_line('{"type":"turn.completed","usage":{"input_tokens":7,'
                '"cached_input_tokens":2,"cache_write_input_tokens":1,'
                '"output_tokens":3}}')
    assert p.usage() == {"turns": 1, "input_tokens": 5, "output_tokens": 3,
                         "cache_read_input_tokens": 2,
                         "cache_creation_input_tokens": 1}
    assert not hasattr(codex_cli, "_record_usage")


def test_a_resumed_spawn_is_billed_only_for_its_own_turns(
    tmp_path: Path,
) -> None:
    """Codex re-reports the WHOLE conversation's totals on every resume,
    and `spawn_usage` sums the rows it is handed. Without a baseline the
    second stage re-bills the first — the 2.0x over-count measured on
    Test.provider_probe on 2026-08-15, where one formalizer's three
    stage rows summed to 1.11M prompt tokens against a session total of
    550,619 (checked against the rollout, which agreed with the LAST row
    exactly).
    """
    from Tooling.llm.stream_parser import StreamParser

    # Stage 1, cold: nothing recorded for this thread yet.
    p1 = StreamParser(dialect="codex",
                      usage_baseline=codex_cli._usage_baseline(
                          tmp_path, None))
    p1.feed_line('{"type":"turn.completed","usage":{"input_tokens":22138,'
                 '"cached_input_tokens":55296,"output_tokens":608}}')
    assert p1.usage()["output_tokens"] == 608
    codex_cli._remember_usage(tmp_path, "th-1", p1.cumulative_usage())

    # Stage 2 resumes it. Codex reports the conversation so far; the
    # spawn spent the difference.
    p2 = StreamParser(dialect="codex",
                      usage_baseline=codex_cli._usage_baseline(
                          tmp_path, "th-1"))
    p2.feed_line('{"type":"turn.completed","usage":{"input_tokens":80347,'
                 '"cached_input_tokens":470272,"output_tokens":3187}}')
    u2 = p2.usage()
    assert u2["output_tokens"] == 3187 - 608
    assert u2["cache_read_input_tokens"] == 470272 - 55296
    # And the two rows now SUM to the session total, which is what a
    # summing ledger needs them to do.
    u1 = p1.usage()
    assert (u1["cache_read_input_tokens"] + u2["cache_read_input_tokens"]
            == 470272)
    assert u1["output_tokens"] + u2["output_tokens"] == 3187


def test_a_cold_thread_carries_no_baseline(tmp_path: Path) -> None:
    """A fresh conversation starts the provider's count at zero, so the
    whole figure belongs to this spawn. The Adversary depends on it: a
    fresh projection per round means a new thread every time."""
    assert codex_cli._usage_baseline(tmp_path, None) == {}
    assert codex_cli._usage_baseline(tmp_path, "never-seen") == {}
    codex_cli._remember_usage(tmp_path, "th-a", {"output_tokens": 5})
    assert codex_cli._usage_baseline(tmp_path, "th-b") == {}
    assert codex_cli._usage_baseline(tmp_path, "th-a") == {"output_tokens": 5}


def test_two_threads_in_one_directory_do_not_cross_bill(
    tmp_path: Path,
) -> None:
    """One pipeline id can carry two conversations — the Strategist's
    and, under it, the judge's. Measured on 08-15: pipeline 40366c8a
    held a 410k strategist session and a 545k adversary session. A
    ledger keyed by pipeline rather than by thread would subtract one
    from the other."""
    codex_cli._remember_usage(tmp_path, "th-strategist",
                              {"output_tokens": 6226})
    codex_cli._remember_usage(tmp_path, "th-adversary",
                              {"output_tokens": 6957})
    assert codex_cli._usage_baseline(tmp_path, "th-strategist") == {
        "output_tokens": 6226}
    assert codex_cli._usage_baseline(tmp_path, "th-adversary") == {
        "output_tokens": 6957}


def test_a_corrupt_ledger_does_not_break_the_spawn(tmp_path: Path) -> None:
    """Telemetry must never fail a spawn: an unreadable ledger means no
    baseline (this spawn over-reports once), not a crash."""
    (tmp_path / codex_cli._USAGE_LEDGER).write_text("{not json",
                                                    encoding="utf-8")
    assert codex_cli._usage_baseline(tmp_path, "th-1") == {}
    codex_cli._remember_usage(tmp_path, "th-1", {"output_tokens": 3})
    assert codex_cli._usage_baseline(tmp_path, "th-1") == {"output_tokens": 3}


def test_a_fully_cached_turn_reports_no_fresh_input() -> None:
    """The shape that made this visible: a resumed codex turn re-sends
    the whole conversation and gets ~97% of it back from cache. Under
    the old mapping that turn read as 35k FRESH tokens plus 34k cached —
    a spawn that never happened, and a cache-hit rate of 49% where the
    truth is 97%."""
    from Tooling.llm.stream_parser import StreamParser
    p = StreamParser(dialect="codex")
    p.feed_line('{"type":"turn.completed","usage":{"input_tokens":35388,'
                '"cached_input_tokens":34560,"output_tokens":166}}')
    u = p.usage()
    assert u["input_tokens"] == 828
    assert u["cache_read_input_tokens"] == 34560
    # The prompt is accounted for exactly once.
    assert u["input_tokens"] + u["cache_read_input_tokens"] == 35388


# ------------------------------------------------------ the home tree

def test_a_missing_credential_stops_the_spawn_instead_of_running_blind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A spawn with no credential would reach the API, fail, and be
    charged to the agent. The envelope builder answering None routes it
    to MISSING_DEP instead."""
    monkeypatch.setattr(codex_cli, "operator_codex_home",
                        lambda: tmp_path / "nowhere")
    assert codex_cli._spawn_home(_req(tmp_path), "m", "xhigh") is None


def test_the_home_carries_exactly_the_credential_and_the_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It lives under attempts_dir for two reasons: the dispatcher's
    orphan sweep is its cleanup, and MEASURED — a CODEX_HOME under the
    system temp dir makes codex refuse to provision its helper
    binaries."""
    operator = tmp_path / "op"
    operator.mkdir()
    (operator / "auth.json").write_text('{"auth_mode":"chatgpt"}',
                                        encoding="utf-8")
    monkeypatch.setattr(codex_cli, "operator_codex_home", lambda: operator)
    req = _req(tmp_path)
    home = codex_cli._spawn_home(req, "gpt-5.6-luna", "xhigh")
    assert home is not None
    assert home.parent == req.attempts_dir
    assert (home / "auth.json").is_file()
    assert "shell_tool = false" in (home / "config.toml").read_text(
        encoding="utf-8")


# --------------------------------------------------- the liveness clock

def test_the_tool_clock_is_real_but_the_stream_clock_is_not() -> None:
    """The clock is chosen by (provider, kind), and codex can serve only
    one of the two. A formalizer's failure is thinking instead of acting,
    which the tool cadence catches. An NL kind's WORK is the thinking,
    and telling "deep in one thought" from "dead" needs sub-tool
    granularity codex does not emit — so it must be told there is no
    clock, not handed the wrong one. Substituting the tool clock here is
    exactly what killed seven healthy strategist spawns on 2026-08-07."""
    from Tooling.llm import capabilities as caps
    assert caps.liveness_clock("codex", "formalizer") == caps.LIVENESS_TOOL
    for nl_kind in ("strategist", "adversary"):
        assert (caps.liveness_clock("codex", nl_kind)
                == caps.LIVENESS_TIMEOUT_ONLY)
    # claude has the deltas, so it keeps both clocks.
    assert caps.liveness_clock("claude", "strategist") == caps.LIVENESS_STREAM
    assert caps.liveness_clock("claude", "formalizer") == caps.LIVENESS_TOOL


def test_the_codex_dialect_drives_the_same_state_machine() -> None:
    from Tooling.llm.stream_parser import ParserState, StreamParser
    p = StreamParser(dialect="codex")
    p.feed_line('{"type":"thread.started","thread_id":"t1"}')
    p.feed_line('{"type":"turn.started"}')
    assert p.snapshot().state is ParserState.IN_MESSAGE
    p.feed_line('{"type":"item.started","item":{"id":"i0",'
                '"type":"mcp_tool_call","tool":"validate_file"}}')
    snap = p.snapshot()
    assert snap.state is ParserState.MID_TOOL
    # …and the tool clock now has a heartbeat to measure from.
    assert snap.last_tool_use_ts is not None
    p.feed_line('{"type":"turn.completed","usage":{"input_tokens":1,'
                '"output_tokens":1}}')
    snap = p.snapshot()
    assert snap.state is ParserState.FINALIZED
    assert snap.last_stop_reason == "end_turn"


def test_a_failed_turn_is_not_a_clean_finish() -> None:
    """The completion-reclaim path terminates a live process when the
    parser says `finalized` + `end_turn`. A failed turn reaching that
    pair would make a crash look like a tidy finish worth salvaging."""
    from Tooling.llm.stream_parser import StreamParser
    p = StreamParser(dialect="codex")
    p.feed_line('{"type":"turn.started"}')
    p.feed_line('{"type":"turn.failed","error":{"message":"400"}}')
    assert p.snapshot().last_stop_reason == "error"


def test_reasoning_does_not_tick_the_tool_clock() -> None:
    """Thinking is precisely what the tool clock exists to distinguish
    from acting; counting it would make the clock unable to fire."""
    from Tooling.llm.stream_parser import ParserState, StreamParser
    p = StreamParser(dialect="codex")
    p.feed_line('{"type":"item.started","item":{"id":"i","type":"reasoning"}}')
    snap = p.snapshot()
    assert snap.state is ParserState.MID_THINKING
    assert snap.last_tool_use_ts is None


def test_the_claude_dialect_is_untouched_by_the_new_one() -> None:
    from Tooling.llm.stream_parser import ParserState, StreamParser
    p = StreamParser()
    p.feed_line(json.dumps({"type": "stream_event", "event": {
        "type": "content_block_start",
        "content_block": {"type": "tool_use"}}}))
    assert p.snapshot().state is ParserState.MID_TOOL
    # …and a codex line means nothing to it, nor a claude line to codex.
    p2 = StreamParser(dialect="codex")
    p2.feed_line(json.dumps({"type": "stream_event", "event": {
        "type": "content_block_start",
        "content_block": {"type": "tool_use"}}}))
    assert p2.snapshot().state is ParserState.IDLE


def test_an_unknown_dialect_is_refused_at_construction() -> None:
    from Tooling.llm.stream_parser import StreamParser
    with pytest.raises(ValueError):
        StreamParser(dialect="gemini")


# ------------------------------------------------ launching the binary

def test_an_npm_shim_is_not_mistaken_for_an_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """npm puts TWO files on PATH: `foo` (a POSIX shell script) and
    `foo.cmd`. `shutil.which` returns the first, and CreateProcess
    cannot run it — `[WinError 193] %1 is not a valid Win32
    application`, raised at Popen and surfaced as a worker exception
    that says nothing about launchability. It cost this provider its
    first live spawn on 2026-08-12.

    Measured the same day: `codex`, `gemini` and `npm` all resolve to
    the extensionless shim on this machine; `claude` and `agy` are
    `.EXE` only by luck of their installers."""
    import os
    from Tooling.llm.base import which_launchable
    if os.name != "nt":
        pytest.skip("the trap is a Windows CreateProcess behaviour")
    (tmp_path / "foo").write_text("#!/bin/sh\n", encoding="utf-8")
    (tmp_path / "foo.cmd").write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT;.CMD")
    got = which_launchable("foo")
    assert got is not None and got.lower().endswith(".cmd")


def test_a_name_with_no_launchable_spelling_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the shim on PATH must read as "not installed", not as a
    path that fails at Popen — the whole point is that the answer is
    decided before a spawn is charged for it."""
    import os
    from Tooling.llm.base import which_launchable
    if os.name != "nt":
        pytest.skip("the trap is a Windows CreateProcess behaviour")
    (tmp_path / "bar").write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT;.CMD")
    assert which_launchable("bar") is None


def test_a_launch_failure_is_infra_not_a_failed_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A CLI that cannot START is not an agent that tried and failed.
    The 2026-08-12 run proved the price of conflating them: a
    `[WinError 193]` escaped as a worker exception, so the framework
    charged the attempt and re-woke the Strategist — four Programme
    debates and ~106k output tokens spent on a provider that had never
    launched once."""
    operator = tmp_path / "op"
    operator.mkdir()
    (operator / "auth.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(codex_cli, "operator_codex_home", lambda: operator)
    monkeypatch.setattr(codex_cli, "resolve_codex_executable",
                        lambda: str(tmp_path / "not-an-exe"))

    def _boom(*a, **kw):
        raise OSError(193, "%1 is not a valid Win32 application")

    monkeypatch.setattr(codex_cli.subprocess, "Popen", _boom)
    from Tooling.llm.base import SpawnRC
    assert codex_cli.CodexCliProvider().spawn(_req(tmp_path)) \
        == SpawnRC.MISSING_DEP


def test_resume_carries_only_the_flags_that_subcommand_accepts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`codex exec` and `codex exec resume` take DIFFERENT option sets.
    Copying the cold line's flags onto the resume line fails the spawn
    in 2.2 seconds with `unexpected argument '-C'` — measured
    2026-08-12, the codex formalizer's second live attempt, which is
    also when the intake turn's ~44k input was paid for nothing.
    `resume` has no -C, no --add-dir, no --sandbox: the resumed turn
    inherits the workspace roots recorded in the session."""
    operator = tmp_path / "op"
    operator.mkdir()
    (operator / "auth.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(codex_cli, "operator_codex_home", lambda: operator)
    monkeypatch.setattr(codex_cli, "resolve_codex_executable",
                        lambda: "codex.cmd")
    seen: dict = {}

    def _capture(cmd, **kw):
        seen["cmd"] = cmd
        raise OSError("stop here — the argv is the whole assertion")

    monkeypatch.setattr(codex_cli.subprocess, "Popen", _capture)
    req = _req(tmp_path, is_retry=True, retry_context="nope")
    codex_cli._remember_thread(req.attempts_dir, req.session_id, "thread-7")
    codex_cli.CodexCliProvider().spawn(req)

    cmd = seen["cmd"]
    assert cmd[1:4] == ["exec", "resume", "thread-7"]
    for rejected in ("-C", "--cd", "--add-dir", "-s", "--sandbox"):
        assert rejected not in cmd, f"{rejected} is not a `resume` option"
    assert "--json" in cmd and cmd[-1] == "-"


def test_the_cold_line_still_grants_the_attempts_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """…and the flags `resume` cannot take must still be on the COLD
    line, or the agent has no writable sandbox at all (`.attempts/<pid>/`
    sits at the workspace root, outside `-C`)."""
    operator = tmp_path / "op"
    operator.mkdir()
    (operator / "auth.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(codex_cli, "operator_codex_home", lambda: operator)
    monkeypatch.setattr(codex_cli, "resolve_codex_executable",
                        lambda: "codex.cmd")
    seen: dict = {}

    def _capture(cmd, **kw):
        seen["cmd"] = cmd
        raise OSError("stop here")

    monkeypatch.setattr(codex_cli.subprocess, "Popen", _capture)
    req = _req(tmp_path)
    codex_cli.CodexCliProvider().spawn(req)
    cmd = seen["cmd"]
    assert "resume" not in cmd
    assert cmd[cmd.index("-C") + 1] == str(req.problem_dir)
    assert cmd[cmd.index("--add-dir") + 1] == str(req.attempts_dir)


# ------------------------------------------------ the transcript lives

def _pipeline(tmp_path: Path) -> "tuple[LLMRequest, Path]":
    """The real on-disk shape: `<workspace>/.attempts/<pipeline_id>/`,
    with the per-spawn CODEX_HOME inside it. The nesting is the whole
    point — that directory is what `WorkArea.__exit__` rmtrees."""
    attempts = tmp_path / ".attempts" / "pid1"
    attempts.mkdir(parents=True)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("do it\n", encoding="utf-8")
    req = LLMRequest(kind="formalizer", prompt_path=prompt,
                     problem_dir=tmp_path / "Problems" / "P",
                     attempts_dir=attempts, timeout_sec=900,
                     session_id="sid-1")
    home = attempts / "_codex_home"
    day = home / "sessions" / "2026" / "08" / "12"
    day.mkdir(parents=True)
    (day / "rollout-2026-08-12T14-00-00-abc.jsonl").write_text(
        '{"type":"session_meta","payload":{"id":"abc"}}\n', encoding="utf-8")
    return req, home


def test_the_reasoning_outlives_the_sandbox(tmp_path: Path) -> None:
    """`WorkArea.__exit__` rmtrees `.attempts/<pid>/`, and the per-spawn
    CODEX_HOME lives inside it — so without this the rollout carrying
    every tool call dies with the attempt. MEASURED the day the provider
    landed: `[feedback] forward/inject3171: spawn rc=1,
    scratch_written=False` and the reason was unknowable, because the
    evidence had already been deleted. claude keeps its transcripts in
    `~/.claude/projects/`, agy in `~/.gemini/.../conversations/`; codex
    gets the same property here."""
    req, home = _pipeline(tmp_path)
    (req.attempts_dir / "_spawn.stderr").write_text("rc=1\nboom",
                                                    encoding="utf-8")
    codex_cli._preserve_transcript(req, home)

    dest = transcript_dest(tmp_path / ".attempts" / "pid1",
                            codex_cli._TRANSCRIPT_DIRNAME)
    assert (dest / "rollout-2026-08-12T14-00-00-abc.jsonl").is_file()
    assert (dest / "_spawn.0.stderr").read_text(
        encoding="utf-8").startswith("rc=1")
    # …and the ORIGINAL stays put. Moving it looks tidier and breaks
    # the next spawn outright: codex resolves a resumed thread by
    # opening that exact path inside CODEX_HOME, so a moved rollout
    # gives `thread/resume failed: failed to resolve rollout path ...
    # file does not exist (code -32600)` — measured, one run after the
    # preservation itself landed.
    assert list((home / "sessions").rglob("rollout-*.jsonl"))


def test_the_copy_is_refreshed_so_it_is_not_a_partial_snapshot(
    tmp_path: Path,
) -> None:
    """A resumed turn appends to the same rollout. Copying once and
    skipping thereafter would preserve the intake turn and lose the work
    turn that followed it."""
    req, home = _pipeline(tmp_path)
    roll = next((home / "sessions").rglob("rollout-*.jsonl"))
    codex_cli._preserve_transcript(req, home)
    roll.write_text(roll.read_text(encoding="utf-8") + '{"type":"more"}\n',
                    encoding="utf-8")
    codex_cli._preserve_transcript(req, home)
    dest = transcript_dest(tmp_path / ".attempts" / "pid1",
                            codex_cli._TRANSCRIPT_DIRNAME) / roll.name
    assert '{"type":"more"}' in dest.read_text(encoding="utf-8")


def test_the_credential_is_not_preserved_with_it(tmp_path: Path) -> None:
    """The home dies on purpose: it holds a copy of the operator's
    `auth.json`, and a credential outliving its attempt is a worse
    problem than the one being fixed."""
    req, home = _pipeline(tmp_path)
    (home / "auth.json").write_text('{"tokens":{}}', encoding="utf-8")
    codex_cli._preserve_transcript(req, home)
    dest = transcript_dest(tmp_path / ".attempts" / "pid1",
                            codex_cli._TRANSCRIPT_DIRNAME)
    assert not (dest / "auth.json").exists()
    assert list(dest.iterdir())


def test_several_spawns_share_a_dir_without_erasing_each_other(
    tmp_path: Path,
) -> None:
    """One attempts_dir hosts intake, the work turn and the feedback
    turn, and each overwrites `_spawn.stderr`. The intake's failure must
    not be erased by the turn that came after it."""
    req, home = _pipeline(tmp_path)
    (req.attempts_dir / "_spawn.stderr").write_text("first", encoding="utf-8")
    codex_cli._preserve_transcript(req, home)
    (req.attempts_dir / "_spawn.stderr").write_text("second", encoding="utf-8")
    codex_cli._preserve_transcript(req, home)
    dest = transcript_dest(tmp_path / ".attempts" / "pid1",
                            codex_cli._TRANSCRIPT_DIRNAME)
    assert (dest / "_spawn.0.stderr").read_text(encoding="utf-8") == "first"
    assert (dest / "_spawn.1.stderr").read_text(encoding="utf-8") == "second"


def test_a_spawn_that_left_nothing_creates_no_empty_directory(
    tmp_path: Path,
) -> None:
    req, home = _pipeline(tmp_path)
    for roll in (home / "sessions").rglob("rollout-*.jsonl"):
        roll.unlink()
    codex_cli._preserve_transcript(req, home)
    assert not transcript_dest(tmp_path / ".attempts" / "pid1",
                            codex_cli._TRANSCRIPT_DIRNAME).exists()


def test_the_cold_line_asks_for_a_writable_sandbox_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`sandbox_mode` in config.toml is not enough: MEASURED 2026-08-12,
    a session whose config said `workspace-write` recorded
    `sandbox_policy: {"type": "read-only"}` in its own turn_context. The
    flag is the thing that takes effect."""
    operator = tmp_path / "op"
    operator.mkdir()
    (operator / "auth.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(codex_cli, "operator_codex_home", lambda: operator)
    monkeypatch.setattr(codex_cli, "resolve_codex_executable",
                        lambda: "codex.cmd")
    seen: dict = {}

    def _capture(cmd, **kw):
        seen["cmd"] = cmd
        raise OSError("stop here")

    monkeypatch.setattr(codex_cli.subprocess, "Popen", _capture)
    codex_cli.CodexCliProvider().spawn(_req(tmp_path))
    cmd = seen["cmd"]
    assert cmd[cmd.index("--sandbox") + 1] == "workspace-write"


# ------------------------------------------------ the intake stage reads

def test_intake_is_dispatched_with_a_reading_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The intake turn's whole job is to READ Context.md and answer.
    It used to be dispatched with no MCP at all — invisible on claude,
    which has a native `Read`, and fatal on codex, which has no file
    tool once the shell is closed. MEASURED 2026-08-12: the codex intake
    rollout shows ZERO tool calls and the agent's final message is
    "the environment is read-only and provides no file-reading tool, so
    I could not inspect `Context.md` or write `intake.json` without
    inventing a verdict." The economy gate then fails open, so the stage
    was a silent no-op that still cost a spawn."""
    from Tooling.pipeline import _intake

    (tmp_path / "Problems").mkdir()
    (tmp_path / "Tooling").mkdir()
    attempts = tmp_path / ".attempts" / "pid1"
    attempts.mkdir(parents=True)
    seen: dict = {}

    def _spawn(**kw):
        seen.update(kw)
        return 1          # degrade; we only care about the dispatch

    monkeypatch.setattr(_intake.agent, "spawn_llm", _spawn)
    _intake.run_intake(prompt_dir=tmp_path / "prompts",
                       attempts_dir=attempts,
                       problem_dir=tmp_path / "Problems" / "P",
                       label="probe", workspace=tmp_path)

    cfg = seen.get("mcp_config_path")
    assert cfg is not None, "intake dispatched with no MCP config"
    servers = json.loads(Path(cfg).read_text(encoding="utf-8"))["mcpServers"]
    assert "asterism_tools" in servers
    # …and NOT the gateway: intake touches no Lean, and registering a
    # session would open a backend slot nobody uses.
    assert "lsp" not in servers


def test_windows_needs_its_sandbox_mode_or_every_write_is_refused(
    tmp_path: Path,
) -> None:
    """MEASURED 2026-08-13, three probes, one variable each:
    `--sandbox workspace-write` alone → "patch rejected: writing is
    blocked by read-only sandbox"; adding `[projects.<cwd>]
    trust_level="trusted"` → identical refusal; adding this line → the
    file appears. The session recorded `sandbox_policy: read-only` in
    every case until this was set.

    It cost the intake sentinel and the feedback record — the two
    artifacts the agent has to write itself. The work turn never noticed
    because its writes go through the gateway MCP, server-side."""
    cfg = codex_cli._render_config(_req(tmp_path), "m", "xhigh")
    assert '[windows]\nsandbox = "unelevated"' in cfg


def test_one_unpreservable_artifact_does_not_drop_the_others(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first version wrapped every copy in ONE try, so a failing
    rollout copy skipped the stderr underneath it — and the stderr was
    the whole reason the helper exists. That is how a feedback failure
    stayed unexplained across three runs (2026-08-13). Best-effort has
    to mean per artifact."""
    req, home = _pipeline(tmp_path)
    (req.attempts_dir / "_spawn.stderr").write_text("the answer",
                                                    encoding="utf-8")
    real = codex_cli.shutil.copyfile

    def _copy(src, dst):
        if str(src).endswith(".jsonl"):
            raise OSError("locked by the exiting process")
        return real(src, dst)

    monkeypatch.setattr(codex_cli.shutil, "copyfile", _copy)
    codex_cli._preserve_transcript(req, home)
    dest = transcript_dest(tmp_path / ".attempts" / "pid1",
                            codex_cli._TRANSCRIPT_DIRNAME)
    assert (dest / "_spawn.0.stderr").read_text(encoding="utf-8") == "the answer"


def test_the_writable_roots_travel_in_the_config_not_only_the_flag(
    tmp_path: Path,
) -> None:
    """`codex exec resume` takes no `--add-dir`: a resumed turn inherits
    what the SESSION recorded, which is only the cwd. MEASURED
    2026-08-13 — the feedback turn resumes, and it reported "the current
    sandbox permits writes only inside <problem_dir>, and no Write tool
    is available", so the record never landed. The work turn never
    noticed: its writes go through the gateway MCP, server-side.

    Config is read on every invocation of the per-spawn home, so the
    roots stated here cover the cold line and the resume alike."""
    req = _req(tmp_path)
    cfg = codex_cli._render_config(req, "m", "xhigh")
    assert "[sandbox_workspace_write]" in cfg
    assert str(req.attempts_dir) in cfg


def test_tools_server_env_carries_the_delivery_ceiling(
    tmp_path: Path,
) -> None:
    """The number rides `[mcp_servers.asterism_tools.env]` because that
    table is the one route PROVEN to reach the server process (the
    server cannot even import `Tooling` without the PYTHONPATH it
    already carries). The JSON config writers run before the provider
    is known, so the codex adapter injects it at render time — and only
    for the tools server; the gateway does not read it."""
    from Tooling.llm import capabilities as caps

    toml = codex_cli._mcp_servers_toml(_mcp_config(tmp_path))
    want = caps.inspect_delivery_chars("codex")
    assert f"ASTERISM_INSPECT_DELIVERY_CHARS = '{want}'" in toml
    assert toml.count("ASTERISM_INSPECT_DELIVERY_CHARS") == 1
    # the entry's own env survives the merge
    assert "PYTHONPATH" in toml


def test_cold_prompt_carries_the_toolface_alignment_note() -> None:
    """codex hard-injects developer guidance mandating apply_patch; the
    asterism tool face has no such tool (12 self-reports of agents
    reconciling the two worlds by guesswork, 2026-08-22). The adapter
    prepends one alignment line on COLD spawns — codex-path only (user
    ruling), so no other provider's prompts ever change."""
    import inspect as _inspect
    from Tooling.llm import codex_cli
    src = _inspect.getsource(codex_cli)
    assert "authoritative toolset" in src
    # the note must be fenced to the non-resume branch
    assert "if not resuming:" in src


def test_zen_turn_budget_margin_scales_with_the_wall(tmp_path: Path) -> None:
    """A flat 300s wrap-up margin (calibrated on the 1800s formalizer)
    starved a 420s presearch to a 120s turn budget — tools locked
    before the first block could be written (friend-fleet report,
    2026-08-23). The margin is a quarter of the wall, capped at 300s,
    floored at 60s."""
    att = tmp_path / ".attempts" / "pid-z"
    att.mkdir(parents=True)
    for wall, want in ((1800, 1500), (420, 315), (240, 180), (120, 60)):
        req = _req(tmp_path, attempts_dir=att, timeout_sec=wall)
        cfg = codex_cli._render_config(req, "x-preview-f-free", "high",
                                       flavor="zen")
        assert f"/b/{want}/v1" in cfg, (wall, cfg)
