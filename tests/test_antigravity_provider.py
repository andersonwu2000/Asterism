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
    rc = agy.AntigravityCliProvider().spawn(_req(tmp_path))
    assert rc == agy.RC_MISCONFIGURED
    assert "wrote NOTHING" in capsys.readouterr().out


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
