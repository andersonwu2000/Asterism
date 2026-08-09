"""Antigravity CLI (`agy`) provider — the subscription path to Gemini
models after Google cut the Gemini CLI's individual tiers off
(2026-06-18).

Pins the behaviours that were measured against agy 1.1.8 on 2026-07-30
and that the old gemini provider got wrong:
  * `status: "SUCCESS"` is NOT proof of work — a tool denied for want of
    a `permissions.allow` rule returns SUCCESS with nothing written.
  * `.json` counts as an agent artifact (the gemini provider's check
    listed only .lean/.md, which would have failed every successful
    Adversary round — verdict.json).
  * A framework session id maps onto agy's minted `conversation_id`, so
    the Strategist revision loop can actually resume; without the map
    the retry must fall back to the full prompt rather than send a bare
    rebuttal to an amnesiac agent.
  * An unusable model slug / refused credential is `provider_
    misconfigured` (rc 123), not the default infra fast-fail — retrying
    a config error forever is the failure mode we are avoiding.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from Tooling.llm import antigravity_cli as agy
from Tooling.llm.base import LLMRequest
from Tooling.state import failures


def _req(tmp_path: Path, **kw) -> LLMRequest:
    attempts = tmp_path / "attempts"
    attempts.mkdir(exist_ok=True)
    prompt = tmp_path / "prompt.md"
    if not prompt.exists():
        prompt.write_text("do the thing\n", encoding="utf-8")
    return LLMRequest(
        kind=kw.pop("kind", "strategist"),
        prompt_path=prompt,
        problem_dir=tmp_path,
        attempts_dir=attempts,
        timeout_sec=kw.pop("timeout_sec", 900),
        **kw,
    )


# ------------------------------------------------------------ envelope

def test_envelope_parsed_from_last_json_line():
    """agy prints human notes BEFORE the envelope (observed: the
    `command`-permission denial note), so the envelope is the last json
    object on stdout, not the first line."""
    out = ('jetski: no output produced — a tool required the "command" '
           'permission that headless mode cannot prompt for\n'
           '{"conversation_id":"abc","status":"SUCCESS","response":"hi",'
           '"num_turns":1,"usage":{"input_tokens":10,"output_tokens":2}}\n')
    env = agy._parse_envelope(out)
    assert env is not None
    assert env["conversation_id"] == "abc" and env["status"] == "SUCCESS"


def test_envelope_none_when_absent():
    assert agy._parse_envelope("total garbage") is None


# ------------------------------------------------------ classification

@pytest.mark.parametrize("error", [
    'invalid model selection (--model "gemini-3-pro"): model '
    'gemini-3-pro is not recognized as a known model or custom model',
    "IneligibleTierError: this client is no longer supported",
    "Permission denied for write_file(D:\\Asterism\\Problems\\x.lean)",
])
def test_config_and_auth_errors_are_misconfigured(error):
    """Every one of these needs an operator edit, so they must not land
    on the default fast-fail path where the daemon retries forever."""
    env = {"status": "ERROR", "error": error}
    assert agy._classify(env, "", 1) == agy.RC_MISCONFIGURED
    assert (failures.rc_to_reason(agy.RC_MISCONFIGURED)
            == "provider_misconfigured")


def test_quota_error_stays_quota():
    env = {"status": "ERROR", "error": "RESOURCE_EXHAUSTED: quota"}
    assert agy._classify(env, "", 1) == agy.RC_QUOTA_EXHAUSTED


def test_own_print_timeout_is_classified_as_timeout(tmp_path: Path):
    """agy's clock is deliberately set to fire before the subprocess
    one so the death arrives as an envelope we can classify — which is
    worth nothing if the classifier does not recognise it. Landing on
    the generic rc=1 skipped the retry helper's timeout branch, so no
    postmortem ran and the next spawn inherited no progress note
    (g7415, 2026-08-07)."""
    env = {"status": "ERROR", "error": "timeout waiting for response"}
    assert agy._classify(env, "", 1) == agy.RC_TIMEOUT
    # ... and the worker path must read that rc as a timeout. (Note the
    # two mappings of 124 are both intended: `_spawn_failure` is the
    # goal-bearing pipelines' reading — the agent held the whole budget,
    # so it burns an attempt AND gets a postmortem; `rc_to_reason` is
    # the Strategist/Adversary channel's, where there is no goal.)
    from Tooling.pipeline import _spawn_failure
    reason, _ = _spawn_failure(agy.RC_TIMEOUT, tmp_path, 900.0)
    assert reason == "agent_timeout"


def test_unknown_error_keeps_process_rc():
    env = {"status": "ERROR", "error": "something else entirely"}
    assert agy._classify(env, "", 7) == 7
    # rc=0 with a non-SUCCESS status is still a failure
    assert agy._classify(env, "", 0) == 1


# --------------------------------------------------- artifact presence

def test_provider_bookkeeping_is_not_an_artifact(tmp_path: Path):
    d = tmp_path / "a"
    d.mkdir()
    (d / "Context.md").write_text("ctx", encoding="utf-8")
    (d / "_parser_state.json").write_text("{}", encoding="utf-8")
    (d / "_agy_session.json").write_text("{}", encoding="utf-8")
    (d / "_spawn.stderr").write_text("x", encoding="utf-8")
    assert not agy._agent_artifact_present(d)


def test_json_output_counts_as_an_artifact(tmp_path: Path):
    """The Adversary's only output is verdict.json — the gemini
    provider's .lean/.md-only check would have called every successful
    judge run a no-output failure."""
    d = tmp_path / "a"
    d.mkdir()
    (d / "verdict.json").write_text("{}", encoding="utf-8")
    assert agy._agent_artifact_present(d)


# ------------------------------------------------------- session map

def test_session_map_round_trip(tmp_path: Path):
    d = tmp_path / "a"
    d.mkdir()
    agy._remember_conversation(d, "sid-1", "conv-9")
    assert agy._load_session_map(d) == {"sid-1": "conv-9"}
    # empty ids are not recorded (a failed cold call has no conversation)
    agy._remember_conversation(d, "sid-2", "")
    assert "sid-2" not in agy._load_session_map(d)


def test_retry_without_a_known_conversation_resends_full_prompt(
    tmp_path: Path,
):
    """Without resume the agent has no memory of what it is being told
    to fix, so a bare rebuttal would waste the round."""
    p = agy.AntigravityCliProvider()
    req = _req(tmp_path, is_retry=True, session_id="sid-x",
               retry_context="your proposal was rejected")
    prompt = p._build_prompt(req)
    assert "=== INSTRUCTIONS ===" in prompt
    assert "do the thing" in prompt


def test_retry_with_known_conversation_sends_short_note(tmp_path: Path):
    p = agy.AntigravityCliProvider()
    req = _req(tmp_path, is_retry=True, session_id="sid-x",
               retry_context="criterion 3 fired")
    agy._remember_conversation(req.attempts_dir, "sid-x", "conv-1")
    prompt = p._build_prompt(req)
    assert "criterion 3 fired" in prompt
    assert "=== INSTRUCTIONS ===" not in prompt


# ------------------------------------------------------------- usage

def test_usage_translated_for_spawn_usage_recorder(tmp_path: Path):
    """agy reports usage directly; map it into the `_parser_state.json`
    shape `runtime._record_spawn_usage` reads, or judge/strategist cost
    silently stops being accounted (#107 / #126)."""
    d = tmp_path / "a"
    d.mkdir()
    agy._record_usage(d, {
        "num_turns": 3,
        "usage": {"input_tokens": 100, "output_tokens": 20,
                  "thinking_tokens": 15, "cache_read_tokens": 7,
                  "total_tokens": 120},
    })
    u = json.loads((d / "_parser_state.json").read_text(
        encoding="utf-8"))["usage"]
    assert u == {"turns": 3, "input_tokens": 100, "output_tokens": 20,
                 "cache_read_input_tokens": 7,
                 "cache_creation_input_tokens": 0}


# ------------------------------------------------------------- spawn

def test_error_envelope_with_artifact_is_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """The converse of THE HAZARD, found by the live acceptance run.

    The model called the `loogle` MCP tool with the wrong argument name,
    the server raised, the model corrected itself and answered — and agy
    still stamped the envelope ERROR and exited 1. Failing there would
    throw away a wake whose work was finished, the same class of loss as
    a tripwire replacing an honest spawn's rc. The artifact decides."""
    monkeypatch.setattr(agy, "resolve_agy_executable", lambda: "agy")

    class _R:
        returncode = 1
        stdout = ('{"conversation_id":"c1","status":"ERROR",'
                  '"response":"Nat.factorial_one",'
                  '"error":"Error in MCP tool execution: validation error",'
                  '"num_turns":1,"usage":{"input_tokens":5,'
                  '"output_tokens":1}}')
        stderr = ""

    monkeypatch.setattr(agy.subprocess, "run", lambda *a, **k: _R())
    req = _req(tmp_path)
    (req.attempts_dir / "decision.json").write_text("{}", encoding="utf-8")
    assert agy.AntigravityCliProvider().spawn(req) == 0
    assert "recovered and left its artifact" in capsys.readouterr().out


def test_error_envelope_without_artifact_still_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """The tolerance is bounded by the artifact — an ERROR that produced
    nothing is still a failed spawn."""
    monkeypatch.setattr(agy, "resolve_agy_executable", lambda: "agy")

    class _R:
        returncode = 1
        stdout = ('{"conversation_id":"c1","status":"ERROR",'
                  '"response":"partial thought","error":"boom",'
                  '"num_turns":1,"usage":{"input_tokens":5,'
                  '"output_tokens":1}}')
        stderr = ""

    monkeypatch.setattr(agy.subprocess, "run", lambda *a, **k: _R())
    assert agy.AntigravityCliProvider().spawn(_req(tmp_path)) != 0


def test_success_with_no_artifact_is_misconfigured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """THE hazard: an Ask-defaulted (unmatched) tool is auto-denied in
    headless mode and the run still says SUCCESS with a confident
    answer. Measured twice on 2026-07-30 — a write that never happened
    reported "DONE"."""
    monkeypatch.setattr(agy, "resolve_agy_executable", lambda: "agy")

    class _R:
        returncode = 0
        stdout = ('{"conversation_id":"c1","status":"SUCCESS",'
                  '"response":"DONE","num_turns":1,'
                  '"usage":{"input_tokens":5,"output_tokens":1}}')
        stderr = ""

    monkeypatch.setattr(agy.subprocess, "run", lambda *a, **k: _R())
    req = _req(tmp_path)
    (req.attempts_dir / "scratch.log").write_text("x", encoding="utf-8")
    rc = agy.AntigravityCliProvider().spawn(req)
    assert rc == agy.RC_MISCONFIGURED
    out = capsys.readouterr().out
    assert "left no usable artifact" in out
    # naming what IS there is the diagnostic: "wrote the wrong file" and
    # "was denied every tool" look identical without it
    assert "scratch.log" in out


def test_success_with_artifact_is_zero_and_records_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(agy, "resolve_agy_executable", lambda: "agy")
    req = _req(tmp_path, session_id="sid-1")
    (req.attempts_dir / "decision.json").write_text("[]", encoding="utf-8")

    class _R:
        returncode = 0
        stdout = ('{"conversation_id":"conv-42","status":"SUCCESS",'
                  '"response":"ok","num_turns":2,'
                  '"usage":{"input_tokens":9,"output_tokens":3}}')
        stderr = ""

    monkeypatch.setattr(agy.subprocess, "run", lambda *a, **k: _R())
    assert agy.AntigravityCliProvider().spawn(req) == 0
    assert agy._load_session_map(req.attempts_dir) == {"sid-1": "conv-42"}


def test_missing_cli_returns_missing_dep(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(agy, "resolve_agy_executable", lambda: None)
    assert (agy.AntigravityCliProvider().spawn(_req(tmp_path))
            == agy.RC_MISSING_CLI)


def test_print_timeout_is_set_from_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """agy's own --print-timeout defaults to 5 MINUTES — a Strategist
    wake would be cut off mid-thought if we let that stand."""
    monkeypatch.setattr(agy, "resolve_agy_executable", lambda: "agy")
    seen: dict = {}

    class _R:
        returncode = 0
        stdout = ('{"conversation_id":"c","status":"SUCCESS",'
                  '"response":"","num_turns":1,"usage":{}}')
        stderr = ""

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        seen["timeout"] = kw.get("timeout")
        return _R()

    monkeypatch.setattr(agy.subprocess, "run", fake_run)
    req = _req(tmp_path, timeout_sec=10800)
    (req.attempts_dir / "decision.json").write_text("[]", encoding="utf-8")
    agy.AntigravityCliProvider().spawn(req)
    assert "--print-timeout" in seen["cmd"]
    assert seen["cmd"][seen["cmd"].index("--print-timeout") + 1] == "10800s"
    # the subprocess wall must outlast agy's own timeout so we get an
    # envelope to classify instead of a hard kill
    assert seen["timeout"] > 10800


def test_permission_bypass_flag_is_never_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """`--dangerously-skip-permissions` would auto-approve every tool
    and void the whole write fence (the deny rules on Problems/ /
    Library/ / Tooling/ are what keep a spawn out of proofs/ and
    Root.lean). Pinned so it cannot be added casually."""
    monkeypatch.setattr(agy, "resolve_agy_executable", lambda: "agy")
    seen: dict = {}

    class _R:
        returncode = 0
        stdout = ('{"conversation_id":"c","status":"SUCCESS",'
                  '"response":"","num_turns":1,"usage":{}}')
        stderr = ""

    monkeypatch.setattr(agy.subprocess, "run",
                        lambda cmd, **kw: (seen.update(cmd=cmd), _R())[1])
    req = _req(tmp_path)
    (req.attempts_dir / "decision.json").write_text("[]", encoding="utf-8")
    agy.AntigravityCliProvider().spawn(req)
    assert "--dangerously-skip-permissions" not in seen["cmd"]
    assert "--mode" not in seen["cmd"]


def test_provider_resolves_by_config_name(monkeypatch: pytest.MonkeyPatch):
    from Tooling import llm
    monkeypatch.setenv("ASTERISM_STRATEGIST_PROVIDER", "antigravity")
    assert isinstance(llm.get_provider(kind="strategist"),
                      agy.AntigravityCliProvider)
    monkeypatch.setenv("ASTERISM_STRATEGIST_PROVIDER", "agy")
    assert isinstance(llm.get_provider(kind="strategist"),
                      agy.AntigravityCliProvider)


# ---------------------------------------------------------------------
# Artifact audit — the repo-complement observation
#
# Retired 2026-08-01: the user-file and `proofs/` digest layers. They
# existed because agy then ran with `command(*)` allowed, and a shell is
# a write channel that routes around the write_file deny rules. Both
# providers are capability-closed now, and neither layer ever enforced
# anything (the baseline pin and the commit chokepoint do). Their tests
# went with them; `test_capability_closure_is_what_retired_the_digest_
# layers` is the tripwire that fires if the premise comes back.
# ---------------------------------------------------------------------

def _audit_workspace(tmp_path: Path) -> "tuple[Path, Path]":
    """A git repo with one problem dir. Returns (workspace, problem_dir).

    A real repo because the instrument IS `git status`: stubbing it
    would test the stub."""
    import subprocess
    pdir = tmp_path / "Problems" / "p"
    (pdir / "proofs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True,
                   capture_output=True)
    return tmp_path, pdir


def test_audit_covers_the_whole_repo_except_the_output_regions(
    tmp_path: Path,
) -> None:
    """What an enumeration misses entirely: a write into `Tooling/`,
    another problem, or `Asterism.yaml` was unwatched, because the old
    guard listed three files and one dir. The complement of the
    framework's own output regions is a rule instead of a list."""
    from Tooling.agent import runtime
    ws, pdir = _audit_workspace(tmp_path)
    before = runtime._repo_status(ws)

    (ws / "Tooling").mkdir()
    (ws / "Tooling" / "hack.py").write_text("x = 1\n", encoding="utf-8")
    (ws / "Problems" / "other").mkdir(parents=True)
    (ws / "Problems" / "other" / "Root.lean").write_text("t\n",
                                                         encoding="utf-8")
    for region in (".attempts", ".asterism", "Papers"):
        (ws / region).mkdir()
        (ws / region / "note.txt").write_text("fine\n", encoding="utf-8")

    found = runtime._artifact_audit(
        kind="strategist", problem_dir=pdir, workspace=ws, problem="p",
        attempts_dir=tmp_path / ".attempts" / "x", before=before)
    assert {v["path"] for v in found} == {"Tooling/hack.py",
                                          "Problems/other/Root.lean"}
    assert {v["layer"] for v in found} == {"repo"}


def test_audit_is_silent_when_only_output_regions_changed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """The normal case, and the one the retired layers kept getting
    wrong: a spawn writes its own sandbox and the framework commits a
    proof, and nothing about that is worth a word."""
    from Tooling.agent import runtime
    ws, pdir = _audit_workspace(tmp_path)
    before = runtime._repo_status(ws)

    (ws / ".attempts").mkdir()
    (ws / ".attempts" / "scratch.md").write_text("work\n", encoding="utf-8")
    (pdir / "proofs" / "L_g.lean").write_text("theorem g : T := trivial\n",
                                              encoding="utf-8")
    (pdir / "Root.lean").write_text("assembled\n", encoding="utf-8")

    assert runtime._artifact_audit(
        kind="formalizer", problem_dir=pdir, workspace=ws, problem="p",
        attempts_dir=tmp_path / ".attempts" / "x", before=before) == []
    assert "artifact-audit" not in capsys.readouterr().out


def test_audit_writes_a_durable_record_not_just_a_log_line(
    tmp_path: Path,
) -> None:
    """A log line only reaches whoever is watching the log — the
    operator, and nobody else (user ruling 07-30). The ledger is the
    input a revert would need, so the detection does not have to be
    rewritten when one gets built."""
    import json
    from Tooling.agent import runtime
    ws, pdir = _audit_workspace(tmp_path)
    before = runtime._repo_status(ws)
    (ws / "Tooling").mkdir()
    (ws / "Tooling" / "hack.py").write_text("x = 1\n", encoding="utf-8")

    runtime._artifact_audit(
        kind="formalizer", problem_dir=pdir, workspace=ws, problem="p",
        attempts_dir=tmp_path / ".attempts" / "abc", before=before)

    rows = [json.loads(ln) for ln in
            (ws / runtime._AUDIT_LEDGER).read_text(
                encoding="utf-8").splitlines() if ln.strip()]
    assert len(rows) == 1
    assert rows[0]["kind"] == "formalizer"
    assert rows[0]["attempts_dir"] == "abc"
    assert rows[0]["violations"][0]["path"] == "Tooling/hack.py"


def test_no_audit_layer_can_fail_a_spawn() -> None:
    """The 07-30 defect was not only the false positive: the check
    replaced the provider's rc, so a spawn that had done real work was
    discarded. Nothing here returns an rc any more."""
    from Tooling.agent import runtime
    assert not hasattr(runtime, "RC_SPAWN_WROTE_OUTSIDE_SANDBOX")
    src = Path(runtime.__file__).read_text(encoding="utf-8")
    audit_call = src.split("_artifact_audit(kind=kind")[1][:200]
    assert "return" not in audit_call.split("return rc")[0]


def test_capability_closure_is_what_retired_the_digest_layers() -> None:
    """The retirement's premise, pinned so it cannot rot silently.

    The user-file and `proofs/` digest sweeps were dropped because no
    agent has a shell or a broad write grant any more: agy denies
    `command(*)`, and the claude side ships an empty Bash allowlist. If
    either is reopened, the artifact audit no longer covers what it used
    to and this test is the place that says so — restore the layers (see
    `_artifact_audit`'s docstring and `git log` for runtime.py) or
    justify the new posture."""
    import json
    from Tooling.llm import antigravity_cli as agy
    from Tooling.llm import claude_cli

    assert claude_cli.DEFAULT_BASH_ALLOWED == "", (
        "a Bash allowlist reopens a write channel the audit no longer "
        "watches")

    # agy's grants live in the user's home, not the repo (they are a
    # user decision — AUTHORIZED OPERATIONS §3). Check them when the
    # machine has them; a CI box legitimately has no agy.
    path = agy.permissions_path()
    if not path.exists():
        pytest.skip("no agy settings on this machine")
    deny = json.loads(path.read_text(encoding="utf-8")).get(
        "permissions", {}).get("deny", [])
    assert "command(*)" in deny, (
        "a shell on the agy side reopens the write channel the "
        "user-file / proofs digest layers used to watch")
    assert "read_url(*)" in deny


# ---------------------------------------------------------------------
# Per-spawn capability envelope (2026-08-01)
#
# agy reads permissions and MCP servers from the home directory and
# nowhere else — no config flag (`agy --help`), and its bundled docs give
# only global and per-plugin scopes. So a per-spawn envelope IS a
# per-spawn HOME. Probed the same day: agy authenticates fine under a
# fake HOME (its credentials do not live there) and reaches an MCP server
# configured there, with only the two config files present.
# ---------------------------------------------------------------------

def _envelope_req(tmp_path: Path, *, mcp: "Path | None") -> "object":
    from Tooling.llm.base import LLMRequest
    att = tmp_path / ".attempts" / "pipe1"
    att.mkdir(parents=True, exist_ok=True)
    return LLMRequest(kind="formalizer", prompt_path=tmp_path / "p.md",
                      problem_dir=Path("D:/Asterism/Problems/x"),
                      attempts_dir=att, timeout_sec=900,
                      mcp_config_path=mcp)


def test_spawn_home_narrows_the_write_root_to_this_spawn(
    tmp_path: Path,
) -> None:
    """The global settings.json allowed `write_file(<repo>/.attempts)` —
    every spawn could write every other spawn's sandbox. claude has been
    per-pipeline since #128; this closes the same gap on agy."""
    import json
    from Tooling.llm import antigravity_cli as agy
    req = _envelope_req(tmp_path, mcp=None)
    home = agy._spawn_home(req)
    assert home is not None
    perms = json.loads(
        (home / ".gemini" / "antigravity-cli" / "settings.json").read_text(
            encoding="utf-8"))["permissions"]
    writes = [a for a in perms["allow"] if a.startswith("write_file(")]
    assert writes == [f"write_file({req.attempts_dir})"]
    assert "command(*)" in perms["deny"] and "read_url(*)" in perms["deny"]
    assert "mcp(*)" in perms["allow"]


def test_spawn_home_carries_the_per_spawn_lsp_server(tmp_path: Path) -> None:
    """The blocker this was built for: `mcp__lsp__validate_file` arrives
    in a per-spawn config carrying that spawn's gateway session token,
    and the provider used to drop it on the floor — a formalizer on agy
    could not type-check a single line it wrote."""
    import json
    from Tooling.llm import antigravity_cli as agy
    att = tmp_path / ".attempts" / "pipe1"
    att.mkdir(parents=True)
    cfg = att / "_mcp_config.json"
    cfg.write_text(json.dumps({"mcpServers": {
        "asterism_tools": {"command": "python"},
        "lsp": {"type": "http", "url": "http://127.0.0.1:9/mcp",
                "headers": {"X-Asterism-Session": "tok-42"}}}}),
        encoding="utf-8")
    home = agy._spawn_home(_envelope_req(tmp_path, mcp=cfg))
    assert home is not None
    servers = json.loads(
        (home / ".gemini" / "config" / "mcp_config.json").read_text(
            encoding="utf-8"))["mcpServers"]
    assert set(servers) == {"asterism_tools", "lsp"}
    assert servers["lsp"]["headers"]["X-Asterism-Session"] == "tok-42"


def test_unbuildable_envelope_fails_loudly(tmp_path: Path) -> None:
    """A config agy never reads looks exactly like a provider with no MCP
    support (07-30). Never silent."""
    from Tooling.llm import antigravity_cli as agy
    att = tmp_path / ".attempts" / "pipe1"
    att.mkdir(parents=True)
    bad = att / "_mcp_config.json"
    bad.write_text("{ this is not json", encoding="utf-8")
    assert agy._spawn_home(_envelope_req(tmp_path, mcp=bad)) is None


def test_spawn_env_points_every_home_variable_at_the_envelope(
    tmp_path: Path,
) -> None:
    """Go's os.UserHomeDir reads USERPROFILE on Windows; other consumers
    read HOME. Setting one is a silent half-move."""
    from Tooling.llm import antigravity_cli as agy
    home = tmp_path / "h"
    env = agy._spawn_env(home)
    assert env["HOME"] == str(home)
    assert env["USERPROFILE"] == str(home)
    assert env["HOMEDRIVE"] == home.drive


def test_both_providers_read_one_definition_of_the_write_roots(
    tmp_path: Path,
) -> None:
    """The point of `llm/envelope.py`: the grants are provider-
    independent, only the dialect differs. A third backend inherits the
    definition instead of adding a third copy."""
    import inspect
    import json
    from Tooling.llm import antigravity_cli as agy
    from Tooling.llm import claude_cli
    from Tooling.llm.envelope import envelope_for

    req = _envelope_req(tmp_path, mcp=None)
    roots = envelope_for(req).write_roots
    assert roots[0] == req.attempts_dir

    home = agy._spawn_home(req)
    perms = json.loads(
        (home / ".gemini" / "antigravity-cli" / "settings.json").read_text(
            encoding="utf-8"))["permissions"]["allow"]
    assert [f"write_file({p})" for p in roots] == [
        a for a in perms if a.startswith("write_file(")]

    src = inspect.getsource(claude_cli.ClaudeCliProvider.spawn)
    assert "envelope_for(" in src, (
        "claude must consume the shared definition, not keep its own list")
