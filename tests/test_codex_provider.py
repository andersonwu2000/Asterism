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


def _rollout(path, rows):
    """A codex rollout carrying `rows` of `(input, cached, output)` as
    the THREAD's running totals — the shape `rollout_usage` reads."""
    lines = []
    for total_in, cached, out in rows:
        lines.append(json.dumps({
            "type": "token_usage_record",
            "payload": {"thread_token_usage": {
                "input_tokens": total_in, "cached_input_tokens": cached,
                "cache_write_input_tokens": 0, "output_tokens": out}}}))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


THREAD = "01a06ed4-3ac4-7aa2-aaf0-7b085bb01583"


def test_a_resumed_spawn_is_billed_only_for_its_own_turns(
    tmp_path: Path,
) -> None:
    """A THREAD's totals grow across every resume and `spawn_usage` sums
    the rows it is handed, so each row has to be that spawn's GROWTH.

    The sequence is the one measured on `judge_continuity/
    strategist_c_r1` (2026-09-07): a historical session, a resumed turn
    on top of it, and a SECOND resumed turn on top of that. The three
    rows must sum to the conversation, and no row may be zero while its
    turn was filing a verdict — which is exactly what the run reported
    (`output_tokens: 0` at r2, all zeros at r3).
    """
    home = tmp_path / "_codex_home"
    roll = (home / "sessions" / "2026" / "09" / "05"
            / f"rollout-2026-09-05T07-49-57-{THREAD}.jsonl")

    # The historical session, before the lab ever woke it.
    _rollout(roll, [(400, 300, 40), (841175, 725120, 13357)])
    baseline = codex_cli.rollout_usage(roll)
    assert baseline == {"input_tokens": 116055,
                        "cache_read_input_tokens": 725120,
                        "cache_creation_input_tokens": 0,
                        "output_tokens": 13357}

    # Turn one, resumed: the file grows and the row is the growth.
    _rollout(roll, [(400, 300, 40), (841175, 725120, 13357),
                    (1798738, 1555968, 22949)])
    after1 = codex_cli.rollout_usage(roll)
    turn1 = codex_cli._usage_delta(after1, baseline)
    assert turn1 == {"input_tokens": 126715,
                     "cache_read_input_tokens": 830848,
                     "cache_creation_input_tokens": 0,
                     "output_tokens": 9592}

    # Turn two, resumed AGAIN — baselined on turn one's end, not on the
    # historical session's, which is the r3 leg that reported nothing.
    _rollout(roll, [(400, 300, 40), (841175, 725120, 13357),
                    (1798738, 1555968, 22949),
                    (2939727, 2542208, 27735)])
    after2 = codex_cli.rollout_usage(roll)
    turn2 = codex_cli._usage_delta(after2, after1)
    assert turn2 == {"input_tokens": 154749,
                     "cache_read_input_tokens": 986240,
                     "cache_creation_input_tokens": 0,
                     "output_tokens": 4786}

    # Every turn produced output, and the rows sum to the conversation.
    assert turn1["output_tokens"] and turn2["output_tokens"]
    for k in ("input_tokens", "cache_read_input_tokens", "output_tokens"):
        assert baseline[k] + turn1[k] + turn2[k] == after2[k]


def test_the_stream_figure_is_the_execs_own_and_carries_no_baseline(
) -> None:
    """WHY THE SUBTRACTION MOVED OFF THE STREAM. `turn.completed.usage`
    runs over the `codex exec` PROCESS, not the thread: the resumed exec
    above reported 957563/830848/9592 into its stream — the GROWTH, not
    the thread total. Subtracting a thread baseline from it is what
    turned `strategist_c_r1`'s r2 leg into `output_tokens: 0` and its r3
    leg into all zeros while both were filing verdicts.

    So the parser takes no baseline, and the only way a measured figure
    reaches it is `adopt_usage`."""
    import inspect

    from Tooling.llm.stream_parser import StreamParser

    assert "usage_baseline" not in inspect.signature(
        StreamParser.__init__).parameters
    p = StreamParser(dialect="codex")
    p.feed_line('{"type":"turn.completed","usage":{"input_tokens":957563,'
                '"cached_input_tokens":830848,"output_tokens":9592}}')
    assert p.usage()["output_tokens"] == 9592, "the exec's own spend"
    p.adopt_usage({"input_tokens": 126715, "output_tokens": 9592,
                   "cache_read_input_tokens": 830848,
                   "cache_creation_input_tokens": 0})
    assert p.usage() == {"turns": 1, "input_tokens": 126715,
                         "output_tokens": 9592,
                         "cache_read_input_tokens": 830848,
                         "cache_creation_input_tokens": 0}


def test_a_killed_spawn_still_reports_what_it_spent(tmp_path: Path) -> None:
    """The stream says nothing when the process is reaped before
    `turn.completed`, and the row used to be zero for the hour it had
    just spent. The rollout is written per API call, so it is there."""
    from Tooling.llm.stream_parser import StreamParser
    roll = _rollout(tmp_path / f"rollout-2026-09-07T00-00-00-{THREAD}.jsonl",
                    [(12558, 0, 114), (458047, 382208, 9774)])
    p = StreamParser(dialect="codex")
    p.feed_line('{"type":"turn.started"}')
    assert p.usage()["output_tokens"] == 0, "the stream knows nothing"
    p.adopt_usage(codex_cli._usage_delta(codex_cli.rollout_usage(roll), {}))
    assert p.usage()["output_tokens"] == 9774
    assert p.usage()["input_tokens"] == 75839


def test_a_baseline_in_the_wrong_coordinates_is_clamped_and_said_out_loud(
    capsys: pytest.CaptureFixture,
) -> None:
    """A component that would go negative means the two figures do not
    count the same thing. Clamping ALONE is how the bug hid: a judge
    that argued for four minutes reported spending nothing, and nothing
    said why."""
    got = codex_cli._usage_delta({"output_tokens": 4786},
                                 {"output_tokens": 22949}, label="adversary")
    assert got["output_tokens"] == 0
    said = capsys.readouterr().out
    assert "output_tokens=-18163" in said and "adversary" in said


def test_a_rollout_with_no_usage_record_means_unknown_not_zero(
    tmp_path: Path,
) -> None:
    """`{}` and `{...: 0}` are different answers: the first leaves the
    stream's figure standing, the second would overwrite it with zero."""
    p = tmp_path / f"rollout-2026-09-07T00-00-00-{THREAD}.jsonl"
    p.write_text('{"type":"session_meta"}\n', encoding="utf-8")
    assert codex_cli.rollout_usage(p) == {}
    assert codex_cli.rollout_usage(tmp_path / "absent.jsonl") == {}


def test_the_threads_rollout_is_found_by_thread_and_by_size(
    tmp_path: Path,
) -> None:
    """One CODEX_HOME holds every conversation the attempts dir ran — a
    resumed judge and the cold postmortem beside it — and a resumed turn
    APPENDS, so the longer copy is the later state."""
    home = tmp_path / "_codex_home"
    _rollout(home / "sessions" / "2026" / "09" / "05"
             / f"rollout-2026-09-05T07-49-57-{THREAD}.jsonl", [(10, 0, 1)])
    big = _rollout(home / "sessions" / "2026" / "09" / "07"
                   / f"rollout-2026-09-07T07-40-19-{THREAD}.jsonl",
                   [(10, 0, 1), (20, 0, 2), (30, 0, 3)])
    _rollout(home / "sessions" / "2026" / "09" / "07"
             / "rollout-2026-09-07T07-41-00-other-thread.jsonl",
             [(999, 0, 999)])
    assert codex_cli._thread_rollout(home, THREAD) == big
    assert codex_cli._thread_rollout(home, "never-seen") is None
    assert codex_cli._thread_rollout(home, None) is None


def test_a_cold_thread_carries_no_baseline(tmp_path: Path) -> None:
    """A fresh conversation starts the provider's count at zero, so the
    whole figure belongs to this spawn. The Adversary depends on it: a
    fresh projection per round means a new thread every time."""
    assert codex_cli._usage_baseline(tmp_path, None) == {}
    assert codex_cli._usage_baseline(tmp_path, "never-seen") == {}
    codex_cli._remember_usage(tmp_path, "th-a", {"output_tokens": 5})
    assert codex_cli._usage_baseline(tmp_path, "th-b") == {}
    assert codex_cli._usage_baseline(tmp_path, "th-a")["output_tokens"] == 5


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
    assert codex_cli._usage_baseline(
        tmp_path, "th-strategist")["output_tokens"] == 6226
    assert codex_cli._usage_baseline(
        tmp_path, "th-adversary")["output_tokens"] == 6957


def test_a_corrupt_ledger_does_not_break_the_spawn(tmp_path: Path) -> None:
    """Telemetry must never fail a spawn: an unreadable ledger means no
    baseline (this spawn over-reports once), not a crash."""
    (tmp_path / codex_cli._USAGE_LEDGER).write_text("{not json",
                                                    encoding="utf-8")
    assert codex_cli._usage_baseline(tmp_path, "th-1") == {}
    codex_cli._remember_usage(tmp_path, "th-1", {"output_tokens": 3})
    assert codex_cli._usage_baseline(tmp_path, "th-1")["output_tokens"] == 3


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


# ------------------------------- the credential is SHARED, never forked
#
# #235, verified in the field 2026-09-04 01:50Z. An OpenAI refresh token
# is single-use: a spawn that refreshes writes the new one back into the
# file it read, and that file used to be a private copy in a directory
# about to be deleted. The operator's own file kept the spent token, so
# every later spawn died in ~3s on "your refresh token was already used"
# — read as `spawn_fast_fail`, ten of which exit the daemon.


def _operator_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                   token: str = "r0") -> Path:
    op = tmp_path / "op"
    op.mkdir(exist_ok=True)
    (op / "auth.json").write_text(
        json.dumps({"auth_mode": "chatgpt",
                    "tokens": {"refresh_token": token}}), encoding="utf-8")
    monkeypatch.setattr(codex_cli, "operator_codex_home", lambda: op)
    return op


@pytest.mark.skipif(__import__("os").name == "nt",
                    reason="a Windows symlink needs a privilege a spawn "
                           "cannot assume; that arrangement is the "
                           "copy + write-back tested below")
def test_the_spawn_shares_the_operators_credential_by_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fix itself: the spawn's `auth.json` IS the operator's file, so
    a rotation lands where the next spawn will read it — the same thing
    several `codex exec` sharing one CODEX_HOME already do. Everything
    else about the home stays per-spawn; only the one file that must not
    be forked is shared."""
    import os
    op = _operator_home(tmp_path, monkeypatch)
    home = codex_cli._spawn_home(_req(tmp_path), "m", "xhigh")
    assert home is not None
    link = home / "auth.json"
    assert link.is_symlink()
    assert Path(os.readlink(link)) == op / "auth.json"
    # …and a write through it reaches the operator's file, which is the
    # entire property the copy did not have.
    link.write_text('{"tokens": {"refresh_token": "rotated"}}',
                    encoding="utf-8")
    assert "rotated" in (op / "auth.json").read_text(encoding="utf-8")
    # The envelope is still this spawn's own.
    assert (home / "config.toml").is_file()


def test_the_posix_branch_asks_for_a_link_to_the_operators_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The DECISION, checkable on a box that grants no symlinks (this
    one, and every unprivileged Windows agent that will run the suite):
    on POSIX the adapter must ask for a link pointing at the operator's
    own `auth.json`, not copy it. The test above proves the resulting
    link really is shared, where the OS allows one to be made."""
    import types
    op = _operator_home(tmp_path, monkeypatch)
    asked: list = []
    # A stand-in `os` for this module alone. Setting the real
    # `os.name` would re-point `pathlib.Path` at PosixPath and every path
    # in the process with it.
    monkeypatch.setattr(codex_cli, "os", types.SimpleNamespace(
        name="posix",
        symlink=lambda src, dst: asked.append((Path(src), Path(dst)))))
    home = tmp_path / "home"
    home.mkdir()
    codex_cli._place_credential(op / "auth.json", home)
    assert asked == [(op / "auth.json", home / "auth.json")]
    # …and NOTHING was copied: the whole point is that no second file
    # holding the refresh token exists.
    assert not (home / "auth.json").exists()


def test_a_box_that_refuses_a_symlink_still_gets_a_working_spawn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Windows needs SeCreateSymbolicLink or developer mode, and some
    filesystems refuse links outright. An adapter that failed to spawn
    there would be a worse bug than the one being fixed, so the copy is
    the documented fallback — and `_return_rotated_credential` is its
    other half."""
    op = _operator_home(tmp_path, monkeypatch)
    monkeypatch.setattr(codex_cli.os, "symlink",
                        lambda *a, **k: (_ for _ in ()).throw(
                            OSError(1314, "A required privilege is not "
                                          "held by the client")))
    home = codex_cli._spawn_home(_req(tmp_path), "m", "xhigh")
    assert home is not None
    auth = home / "auth.json"
    assert auth.is_file() and not auth.is_symlink()
    assert auth.read_bytes() == (op / "auth.json").read_bytes()


def test_placing_the_credential_twice_replaces_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The re-sync before the retry runs over whatever the last attempt
    left — including a DANGLING symlink, which `exists()` reports as
    absent and `os.symlink` would then refuse with FileExistsError."""
    op = _operator_home(tmp_path, monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    (home / "auth.json").write_text("stale copy", encoding="utf-8")
    codex_cli._place_credential(op / "auth.json", home)
    codex_cli._place_credential(op / "auth.json", home)
    assert (home / "auth.json").read_text(
        encoding="utf-8") == (op / "auth.json").read_text(encoding="utf-8")


def _copied_home(tmp_path: Path, body: str, *, newer: bool = True) -> Path:
    """The Windows arrangement, on any platform: a real file, not a link."""
    import os
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    auth = home / "auth.json"
    auth.write_text(body, encoding="utf-8")
    ref = (tmp_path / "op" / "auth.json").stat().st_mtime
    os.utime(auth, (ref + 10, ref + 10) if newer else (ref - 10, ref - 10))
    return home


def test_the_windows_copy_returns_a_rotated_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without this, a Windows spawn buries the only live refresh token
    in the directory `WorkArea.__exit__` is about to rmtree — which is
    the whole incident, one platform at a time."""
    op = _operator_home(tmp_path, monkeypatch, token="r0")
    home = _copied_home(tmp_path, json.dumps(
        {"auth_mode": "chatgpt", "tokens": {"refresh_token": "r1"}}))
    codex_cli._return_rotated_credential(home)
    back = json.loads((op / "auth.json").read_text(encoding="utf-8"))
    assert back["tokens"]["refresh_token"] == "r1"


def test_an_unchanged_copy_is_not_written_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ordinary case — every spawn that never had to refresh. Writing
    anyway would churn the operator's file and move its mtime, which is
    the tie-breaker the concurrent case depends on."""
    op = _operator_home(tmp_path, monkeypatch)
    before = (op / "auth.json").stat().st_mtime
    home = _copied_home(tmp_path, (op / "auth.json").read_text(
        encoding="utf-8"))
    codex_cli._return_rotated_credential(home)
    assert (op / "auth.json").stat().st_mtime == before


def test_a_newer_operator_file_wins_over_this_spawns_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sibling spawn (or the operator's own `codex login`) rotated
    after we took our copy: ours is the stale one now, and writing it
    back would spend their live token — the original bug, inverted."""
    op = _operator_home(tmp_path, monkeypatch, token="fresh")
    home = _copied_home(tmp_path, json.dumps(
        {"tokens": {"refresh_token": "ours"}}), newer=False)
    codex_cli._return_rotated_credential(home)
    assert "fresh" in (op / "auth.json").read_text(encoding="utf-8")


def test_an_empty_or_unparseable_copy_is_never_written_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A truncated or half-written `auth.json` handed back to the
    operator's home is a signed-out machine — a worse outage than the one
    being fixed. The gate is SHAPE, never content: a JSON object carrying
    a refresh token or an API key."""
    op = _operator_home(tmp_path, monkeypatch, token="good")
    for junk in ("", "   ", "{not json", "{}", "[]", "null",
                 '{"tokens": {}}', '{"tokens": {"refresh_token": ""}}'):
        home = _copied_home(tmp_path, junk)
        codex_cli._return_rotated_credential(home)
        assert "good" in (op / "auth.json").read_text(encoding="utf-8")
    # …and an API-key credential, which carries no `tokens` map at all,
    # IS a valid shape.
    home = _copied_home(tmp_path, json.dumps({"OPENAI_API_KEY": "sk-x"}))
    codex_cli._return_rotated_credential(home)
    assert "sk-x" in (op / "auth.json").read_text(encoding="utf-8")


def test_the_write_back_is_atomic_and_leaves_no_debris(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """tmp + `os.replace`, so the status reader (a separate process) sees
    the old credential or the new one and never a half-written one. A
    failed replace must leave neither a partial file nor a stray tmp
    carrying the token."""
    op = _operator_home(tmp_path, monkeypatch, token="r0")
    home = _copied_home(tmp_path, json.dumps(
        {"tokens": {"refresh_token": "r1"}}))
    seen: list = []
    real_replace = codex_cli.os.replace

    def _watch(src, dst):
        # The destination still holds the ORIGINAL at this point — the
        # new bytes are entirely in the tmp file.
        seen.append(Path(dst).read_text(encoding="utf-8"))
        return real_replace(src, dst)

    monkeypatch.setattr(codex_cli.os, "replace", _watch)
    codex_cli._return_rotated_credential(home)
    assert seen and "r0" in seen[0]
    assert "r1" in (op / "auth.json").read_text(encoding="utf-8")

    # …and a replace that fails takes the tmp file with it.
    def _boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(codex_cli.os, "replace", _boom)
    _copied_home(tmp_path, json.dumps({"tokens": {"refresh_token": "r2"}}))
    codex_cli._return_rotated_credential(home)
    assert sorted(p.name for p in op.iterdir()) == ["auth.json"]
    assert "r1" in (op / "auth.json").read_text(encoding="utf-8")


def test_a_shared_credential_is_never_written_back_over_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On POSIX the spawn writes THROUGH the link, so there is nothing to
    carry — the write-back is the copy arrangement's other half, not a
    second mechanism running beside it."""
    op = _operator_home(tmp_path, monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    try:
        codex_cli.os.symlink(op / "auth.json", home / "auth.json")
    except OSError:
        pytest.skip("this box does not grant symlinks")
    codex_cli._return_rotated_credential(home)
    assert (home / "auth.json").is_symlink()
    assert "r0" in (op / "auth.json").read_text(encoding="utf-8")


# ---------------------------------- one retry, then the operator is told

def _spent_stderr() -> str:
    """Verbatim from the incident — see `tests/test_spawn_fast_fail.py`
    for the full capture."""
    return ("Your access token could not be refreshed because your "
            "refresh token was already used. Please log out and sign in "
            "again.")


def _stub_launches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                   outcomes: "list[tuple[int, str | None]]") -> list:
    """Let `spawn` reach `_run_proc` with no codex on the box.

    Each launch consumes one outcome, so the LENGTH of the returned list
    is the assertion: how many times the adapter went back."""
    _operator_home(tmp_path, monkeypatch)
    monkeypatch.setattr(codex_cli, "resolve_codex_executable",
                        lambda: "codex.cmd")
    monkeypatch.setattr(codex_cli, "create_capped_job", lambda *a, **k: None)
    monkeypatch.setattr(codex_cli, "assign_to_job", lambda *a, **k: False)
    monkeypatch.setattr(codex_cli.subprocess, "Popen",
                        lambda *a, **kw: object())
    from Tooling.llm import claude_cli
    monkeypatch.setattr(claude_cli, "track_proc", lambda *a, **k: None)
    monkeypatch.setattr(claude_cli, "untrack_proc", lambda *a, **k: None)
    calls: list = []

    def _fake(self, req, proc, prompt, home, **kw):
        rc, body = outcomes[len(calls)]
        calls.append(str(home))
        if body is not None:
            codex_cli._write_spawn_stderr(req.attempts_dir, body, rc)
        return rc

    monkeypatch.setattr(codex_cli.CodexCliProvider, "_run_proc", _fake)
    return calls


def _ws_req(tmp_path: Path) -> "LLMRequest":
    """The real on-disk shape — `<ws>/.attempts/<pid>/` — because the
    degraded ledger is found by walking up to the `.attempts` anchor."""
    att = tmp_path / ".attempts" / "pid1"
    att.mkdir(parents=True)
    return _req(tmp_path, attempts_dir=att)


def test_a_spent_credential_buys_one_retry_and_can_recover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worth taking because the operator's file may have moved UNDER us:
    on Windows a sibling spawn's write-back puts a live token there in
    the seconds this one spent dying. A recovered retry is an ordinary
    success and must degrade nothing."""
    from Tooling.core import degraded
    calls = _stub_launches(tmp_path, monkeypatch,
                           [(1, _spent_stderr()), (0, None)])
    assert codex_cli.CodexCliProvider().spawn(_ws_req(tmp_path)) == 0
    assert len(calls) == 2
    assert degraded.snapshot(tmp_path) == {}


def test_a_second_spent_credential_names_codex_login_in_daemon_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Twice in a row is not a race: the credential really is spent, and
    no copy of the file revives it. `daemon status` renders the degraded
    ledger, so the hourly patrol sees the one command that fixes this
    without reading a run log."""
    from Tooling.core import degraded
    calls = _stub_launches(
        tmp_path, monkeypatch,
        [(1, _spent_stderr()), (1, _spent_stderr()), (1, "never reached")])
    codex_cli.CodexCliProvider().spawn(_ws_req(tmp_path))
    assert len(calls) == 2, "one retry, not a loop"
    entry = degraded.snapshot(tmp_path)["codex_auth_stale"]
    assert entry["count"] == 1
    assert "codex login" in entry["last_detail"]


def test_an_ordinary_death_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The retry is bought by the credential marker alone. Any other
    failure keeps its single spawn — a free extra attempt per death is
    exactly the kind of quiet budget leak this project audits for."""
    calls = _stub_launches(tmp_path, monkeypatch,
                           [(1, "lake build failed"), (0, None)])
    assert codex_cli.CodexCliProvider().spawn(_ws_req(tmp_path)) == 1
    assert len(calls) == 1


def test_the_adapter_and_the_classifier_read_one_predicate() -> None:
    """The adapter decides whether to re-sync and retry; the pipeline
    decides whether the row is `codex_auth_stale`. Two spellings of "is
    this the credential?" is how they come to disagree — so there is one,
    in the leaf module both can import."""
    import inspect
    from Tooling.state import failures
    src = inspect.getsource(codex_cli._died_on_a_spent_credential)
    assert "is_credential_failure" in src
    assert failures.is_credential_failure(_spent_stderr())


def test_zen_has_no_credential_to_re_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The zen flavour authenticates by API key and must have NO
    auth.json at all — a ChatGPT credential there routes codex to the
    subscription backend and 400s (measured 2026-08-22). So the retry,
    which would place one, must not fire for it."""
    calls = _stub_launches(tmp_path, monkeypatch,
                           [(1, _spent_stderr()), (0, None)])
    provider = codex_cli.CodexCliProvider(flavor="zen")
    assert provider.spawn(_ws_req(tmp_path)) == 1
    assert len(calls) == 1


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


def test_a_successful_leg_does_not_inherit_the_last_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`_write_spawn_stderr` writes only on failure and nothing removed
    the file, so the leg AFTER a failure was preserved carrying the
    failure's text: `33082620`'s `_spawn.2/3/4.stderr` all read "rc=124
    TimeoutExpired" for legs that succeeded (2026-09-07). The spawn
    clears the file first, so an absent slot is the truthful record."""
    from Tooling.llm.base import clear_spawn_stderr
    req, home = _pipeline(tmp_path)
    # leg 1 dies
    codex_cli._write_spawn_stderr(req.attempts_dir, "TimeoutExpired", 124)
    codex_cli._preserve_transcript(req, home)
    # leg 2 succeeds — the spawn's first act, with no failure to record
    clear_spawn_stderr(req.attempts_dir)
    codex_cli._preserve_transcript(req, home)
    dest = transcript_dest(tmp_path / ".attempts" / "pid1",
                            codex_cli._TRANSCRIPT_DIRNAME)
    assert (dest / "_spawn.0.stderr").read_text(
        encoding="utf-8").startswith("rc=124")
    assert not (dest / "_spawn.1.stderr").exists()
    # and the next failing leg gets slot 1, its own text
    codex_cli._write_spawn_stderr(req.attempts_dir, "boom", 1)
    codex_cli._preserve_transcript(req, home)
    assert (dest / "_spawn.1.stderr").read_text(
        encoding="utf-8") == "rc=1\nboom"


def test_every_cli_provider_clears_the_previous_legs_stderr(
    tmp_path: Path,
) -> None:
    """One attempts dir, several spawns, one filename — so the clear
    belongs at the top of EVERY adapter's spawn, not just the one whose
    numbered slots made the staleness visible."""
    import inspect
    from Tooling.llm import antigravity_cli, claude_cli
    for provider in (codex_cli.CodexCliProvider,
                     claude_cli.ClaudeCliProvider,
                     antigravity_cli.AntigravityCliProvider):
        src = inspect.getsource(provider.spawn)
        assert "clear_spawn_stderr(req.attempts_dir)" in src, (
            f"{provider.__name__}.spawn keeps whatever the previous leg "
            f"left in _spawn.stderr")
    # the helper itself: gone, and silent when there was nothing there
    from Tooling.llm.base import SPAWN_STDERR, clear_spawn_stderr
    (tmp_path / SPAWN_STDERR).write_text("old", encoding="utf-8")
    clear_spawn_stderr(tmp_path)
    assert not (tmp_path / SPAWN_STDERR).exists()
    clear_spawn_stderr(tmp_path)
    clear_spawn_stderr(tmp_path / "does" / "not" / "exist")


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


def test_project_docs_are_not_read_into_the_spawn(tmp_path: Path) -> None:
    """codex reads every `AGENTS.md` from the cwd up to the git root as
    instructions. Our spawns run under `.attempts/<pid>/` INSIDE the
    repo, so a stray root `AGENTS.md` — the frontend collaborator's
    rulebook, untracked, created 2026-08-25 — became the FIRST user
    message of every local codex wake since (measured on the 2026-08-26
    strategist + judge rollouts that minted fin10). Instructions come
    from the framework's prompt alone: the project-doc reader is off,
    at the top level (a key after a [table] header silently belongs to
    that table)."""
    cfg = codex_cli._render_config(_req(tmp_path), "m", "xhigh")
    assert "project_doc_max_bytes = 0" in cfg
    assert cfg.index("project_doc_max_bytes = 0") < cfg.index("[features]")


# ------------------------------------------- the NL seats' idle clock

def _nl_cfg(tmp_path: Path, *, kind: str = "theorist",
            timeout_sec: int = 10800) -> str:
    return codex_cli._render_config(
        _req(tmp_path, kind=kind, timeout_sec=timeout_sec),
        "gpt-6-astra", "xhigh")


def test_an_nl_seat_gets_its_own_wall_as_the_streams_idle_clock(
    tmp_path: Path,
) -> None:
    """MEASURED 2026-09-05 on 0.153.0. codex kills a turn whose stream
    has been idle for `stream_idle_timeout_ms` and reconnects
    `stream_max_retries` times; the framework set neither, so the
    defaults ran. union_closed g691: two gpt-6-astra/xhigh Theorist
    wakes died as `Reconnecting... 5/5 (stream disconnected before
    completion: idle timeout waiting for websocket)` — the 5/5 IS the
    default retry count — and one had already written its document.

    An NL seat's work is the silence (`capabilities.STREAM_IDLE_KINDS`
    is the framework's own name for the kinds whose thinking cannot be
    read as cadence), so the idle clock must never be the binding one:
    it is the SEAT'S OWN WALL, derived from the request rather than
    written here, so raising a seat's budget raises this with it and no
    second constant can drift from the first (owner ruling
    2026-09-05)."""
    cfg = _nl_cfg(tmp_path, timeout_sec=10800)
    assert "stream_idle_timeout_ms = 10800000" in cfg
    assert "stream_max_retries = 10" in cfg
    assert "request_max_retries = 10" in cfg
    # derived, not a constant: a different wall renders a different clock
    assert "stream_idle_timeout_ms = 7200000" in _nl_cfg(
        tmp_path, kind="theory_reviewer", timeout_sec=7200)


def test_the_nl_provider_is_renamed_because_openai_is_reserved(
    tmp_path: Path,
) -> None:
    """MEASURED 2026-09-05: `[model_providers.openai]` is refused
    OUTRIGHT — `Error loading config.toml: model_providers contains
    reserved built-in provider IDs: 'openai'. Built-in providers cannot
    be overridden.` — so the three keys can only ride a renamed
    provider, and the renamed one has to carry the built-in's own
    fields itself. Each of these was measured, not guessed:

      requires_openai_auth  ChatGPT auth (auth.json carries `tokens`
                            and a NULL OPENAI_API_KEY; no env key was
                            set) authenticated and answered.
      supports_websockets   without it the transport silently drops to
                            SSE — the probe's error said "idle timeout
                            waiting for SSE" where production said
                            "waiting for websocket".
      base_url / wire_api   the ChatGPT backend's own, since a custom
                            provider derives neither.
    """
    cfg = _nl_cfg(tmp_path)
    assert "[model_providers.openai]" not in cfg
    assert "[model_providers.openai-nl]" in cfg
    assert 'model_provider = "openai-nl"' in cfg
    assert "requires_openai_auth = true" in cfg
    assert "supports_websockets = true" in cfg
    assert "https://chatgpt.com/backend-api/codex" in cfg
    assert 'wire_api = "responses"' in cfg
    # TOML: a top-level key after a [table] header belongs to that table
    assert cfg.index('model_provider = "openai-nl"') < cfg.index("[features]")


def test_a_tool_seat_stays_on_the_built_in_provider(
    tmp_path: Path,
) -> None:
    """The renaming is a cost — our config then owns a copy of the
    vendor's endpoint — and it buys nothing for a seat whose liveness
    the tool clock already measures. Only `STREAM_IDLE_KINDS` pays it."""
    from Tooling.llm import capabilities as _caps

    cfg = codex_cli._render_config(_req(tmp_path, kind="formalizer"),
                                   "m", "xhigh")
    assert "model_provider" not in cfg
    assert "[model_providers." not in cfg
    assert "formalizer" not in _caps.STREAM_IDLE_KINDS


def test_the_zen_flavor_keeps_its_own_provider(tmp_path: Path) -> None:
    """Zen routes through the shim and states its own provider; an NL
    seat on zen must not end up declaring two."""
    att = tmp_path / ".attempts" / "pid-z2"
    att.mkdir(parents=True)
    cfg = codex_cli._render_config(
        _req(tmp_path, kind="theorist", attempts_dir=att),
        "x-preview-f-free", "high", flavor="zen")
    assert 'model_provider = "zen"' in cfg
    assert "openai-nl" not in cfg
