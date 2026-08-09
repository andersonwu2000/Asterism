"""Provider capability declarations, and the consumers that read them.

The point of `llm/capabilities.py` is that core stops asking "is this
provider called 'antigravity'?" and starts asking "does this provider
say it can answer?". A declaration nobody reads is worse than none, so
every test below pins a CONSUMER against the declaration — each one
flips a field on a stand-in provider and asserts the consumer's
behaviour follows the field rather than the name.
"""
from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest

from Tooling.llm import capabilities as caps
from Tooling.llm.base import LLMRequest


@pytest.fixture(autouse=True)
def _clean_warning_state():
    caps._reset_warned_for_tests()
    yield
    caps._reset_warned_for_tests()


def _declared(name: str, **kw) -> caps.ProviderCapabilities:
    base = dict(rc_contract=caps.RC_STRUCTURED)
    base.update(kw)
    return caps.ProviderCapabilities(name=name, **base)


# ---------------------------------------------------------------------
# 1. `undeclared` is representable, and is the DEFAULT
# ---------------------------------------------------------------------

def test_a_new_provider_declares_nothing_by_default() -> None:
    """The whole reason the tri-state exists. `codex` is next in line;
    it must not inherit a safe-looking value it never gave."""
    fresh = caps.ProviderCapabilities(name="codex")
    assert fresh.rc_contract == caps.RC_UNDECLARED
    assert fresh.declared is False
    # …and every other field is the pessimistic reading too.
    assert fresh.usage_endpoint is False
    assert fresh.stream_events is False
    assert fresh.session_resume == caps.RESUME_UNDECLARED
    assert fresh.enforcement_strength == caps.ENFORCEMENT_UNDECLARED
    assert fresh.tested_version is None


def test_an_unknown_provider_gets_undeclared_not_a_permissive_default(
) -> None:
    """A provider with no entry at all must not silently read as
    claude. `capabilities_for` never raises and never returns None —
    the caller would otherwise have to invent a policy for the miss,
    which is the 2026-08-07 lookup-miss class (a plausible None that
    silently disabled two halves of the quota ledger)."""
    unknown = caps.capabilities_for("some-cli-nobody-measured")
    assert unknown.declared is False
    assert unknown.rc_contract == caps.RC_UNDECLARED
    assert unknown.usage_endpoint is False
    assert unknown.stream_events is False


def test_every_shipped_provider_declares_an_rc_contract() -> None:
    for name, c in caps.CAPABILITIES.items():
        assert c.declared, f"{name} has no rc contract declared"
        assert c.name == name


def test_aliases_resolve_to_the_canonical_declaration() -> None:
    assert caps.capabilities_for("agy") is caps.CAPABILITIES["antigravity"]
    assert caps.capabilities_for(None) is caps.CAPABILITIES["claude"]


def test_undeclared_warning_fires_once_and_names_the_provider(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert caps.warn_if_undeclared("codex", context="unit test") is True
    first = capsys.readouterr().out
    assert "[capabilities]" in first and "codex" in first
    # …and repeats do not spam the run log.
    assert caps.warn_if_undeclared("codex") is True
    assert capsys.readouterr().out == ""
    # A declared provider never warns.
    assert caps.warn_if_undeclared("claude") is False


def test_marker_tables_named_by_a_declaration_actually_exist() -> None:
    """`tested_version` is only meaningful if it is bound to something.
    Every dotted path a provider claims its version validated must
    resolve to a real, non-empty string-match table — otherwise the
    drift warning points at a name that no longer exists."""
    for name, c in caps.CAPABILITIES.items():
        for dotted in c.marker_tables:
            mod_name, attr = dotted.rsplit(".", 1)
            mod = importlib.import_module(mod_name)
            assert hasattr(mod, attr), f"{name}: {dotted} is gone"
            value = getattr(mod, attr)
            assert value, f"{name}: {dotted} is empty"


# ---------------------------------------------------------------------
# 2. Consumer — core/quota.py reads `usage_endpoint`, not the name
# ---------------------------------------------------------------------

def test_quota_registry_wires_probes_from_the_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two stand-in providers with the SAME kind of name and OPPOSITE
    declarations. The registry must follow the field."""
    from Tooling.core import quota

    def _stub() -> list:
        return []

    monkeypatch.setitem(caps.CAPABILITIES, "prov_yes",
                        _declared("prov_yes", usage_endpoint=True))
    monkeypatch.setitem(caps.CAPABILITIES, "prov_no",
                        _declared("prov_no", usage_endpoint=False))
    monkeypatch.setitem(quota._ENDPOINT_PROBES, "prov_yes", _stub)
    monkeypatch.setattr(quota, "_PROBES", dict(quota._PROBES))

    quota.register_declared_probes()
    assert quota._PROBES["prov_yes"] is _stub
    assert quota._PROBES["prov_no"] is quota._no_endpoint


def test_a_provider_claiming_an_endpoint_with_no_probe_is_loud(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """The gap the old three-literal registry could not express: a
    declaration that promises a usage endpoint nobody implemented would
    otherwise be indistinguishable from a provider that is simply
    fine."""
    from Tooling.core import quota
    monkeypatch.setitem(caps.CAPABILITIES, "prov_claims",
                        _declared("prov_claims", usage_endpoint=True))
    monkeypatch.setattr(quota, "_PROBES", dict(quota._PROBES))
    quota.register_declared_probes()
    out = capsys.readouterr().out
    assert "prov_claims" in out and "implements no probe" in out
    assert quota._PROBES["prov_claims"] is quota._no_endpoint


def test_an_undeclared_provider_gets_no_quota_probe() -> None:
    """`usage_endpoint` defaults False, so an unmeasured backend lands
    in the honest empty case rather than being asked a question it
    cannot answer."""
    from Tooling.core import quota
    assert caps.capabilities_for("codex").usage_endpoint is False
    # the live wiring for the shipped no-endpoint providers
    assert quota._PROBES["antigravity"] is quota._no_endpoint
    assert quota._PROBES["openai"] is quota._no_endpoint
    assert quota._PROBES["claude"] is quota._claude_blocks


# ---------------------------------------------------------------------
# 3. Consumer — the liveness clock reads `stream_events`
# ---------------------------------------------------------------------

def test_liveness_clock_follows_stream_events_not_the_provider_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert caps.liveness_clock("claude", "strategist") == caps.LIVENESS_STREAM
    assert caps.liveness_clock("claude", "formalizer") == caps.LIVENESS_TOOL
    # agy emits one envelope at the end: no stream, therefore no silence
    # clock at all — for EVERY kind, including the NL ones.
    assert (caps.liveness_clock("antigravity", "strategist")
            == caps.LIVENESS_TIMEOUT_ONLY)
    assert (caps.liveness_clock("antigravity", "formalizer")
            == caps.LIVENESS_TIMEOUT_ONLY)
    # Flip the DECLARATION and the answer moves with it.
    monkeypatch.setitem(
        caps.CAPABILITIES, "claude",
        _declared("claude", stream_events=False))
    assert (caps.liveness_clock("claude", "strategist")
            == caps.LIVENESS_TIMEOUT_ONLY)


def test_an_undeclared_provider_gets_the_timeout_only_clock() -> None:
    assert (caps.liveness_clock("codex", "formalizer")
            == caps.LIVENESS_TIMEOUT_ONLY)


def _claude_req(tmp_path: Path) -> LLMRequest:
    att = tmp_path / "att"
    att.mkdir(exist_ok=True)
    p = tmp_path / "prompt.md"
    p.write_text("do it\n", encoding="utf-8")
    return LLMRequest(kind="formalizer", prompt_path=p,
                      problem_dir=tmp_path, attempts_dir=att,
                      timeout_sec=900, session_id="sid-1")


def test_claude_starts_no_watchdog_when_the_declaration_says_no_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The degradation is WIRED, not merely declared: with
    `stream_events=False` the spawn must drop stream-json (there is
    nothing to parse) instead of starting a watchdog thread that
    samples an empty parser for the whole budget."""
    from Tooling.llm import claude_cli

    seen: dict = {}

    class _P:
        returncode = 0
        stdout: list = []
        stderr: list = []

        def communicate(self, timeout=None):
            return ("", "")

        def wait(self, timeout=None):
            return 0

        def poll(self):
            return 0

    def _popen(cmd, **kw):
        seen["cmd"] = cmd
        return _P()

    monkeypatch.setattr(claude_cli.shutil, "which", lambda _n: "claude")
    monkeypatch.setattr(claude_cli.subprocess, "Popen", _popen)

    claude_cli.ClaudeCliProvider().spawn(_claude_req(tmp_path))
    assert "stream-json" in seen["cmd"], "baseline: claude does stream"

    monkeypatch.setitem(
        caps.CAPABILITIES, "claude",
        _declared("claude", stream_events=False))
    claude_cli.ClaudeCliProvider().spawn(_claude_req(tmp_path))
    assert "stream-json" not in seen["cmd"]
    assert seen["cmd"][seen["cmd"].index("--output-format") + 1] == "text"


def test_watchdog_silence_metric_comes_from_the_declaration() -> None:
    """The kind table moved into `capabilities`; `claude_cli` keeps the
    historical name as a re-export so the watchdog tests still bind to
    one definition."""
    from Tooling.llm import claude_cli
    assert claude_cli._STREAM_IDLE_KINDS is caps.STREAM_IDLE_KINDS


# ---------------------------------------------------------------------
# 4. Consumer — rc classification reads `rc_contract`
# ---------------------------------------------------------------------

def test_rc_residue_reading_follows_the_contract() -> None:
    from Tooling.state import failures
    # Framework vocabulary: provider-independent, unchanged.
    for contract in (None, "structured", "uninformative", "undeclared"):
        assert failures.rc_to_reason(124, rc_contract=contract) \
            == "transient_timeout"
        assert failures.rc_to_reason(126, rc_contract=contract) \
            == "quota_exhausted"
        assert failures.rc_to_reason(125, rc_contract=contract) \
            == "spawn_fast_fail"
    # The RESIDUE is where the contract bites.
    assert failures.rc_to_reason(1, rc_contract="structured") \
        == "spawn_fast_fail"
    assert failures.rc_to_reason(1, rc_contract="uninformative") \
        == "unclassified_spawn_failure"
    assert failures.rc_to_reason(1, rc_contract="undeclared") \
        == "unclassified_spawn_failure"
    # A caller with no provider in hand keeps the historical reading.
    assert failures.rc_to_reason(1) == "spawn_fast_fail"


def test_strategist_and_adversary_read_their_own_seats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two seats sit on different providers routinely. An rc from
    the judge must be read against the JUDGE's contract."""
    from Tooling.pipeline import adversary, strategist
    monkeypatch.setenv("ASTERISM_STRATEGIST_PROVIDER", "claude")
    monkeypatch.setenv("ASTERISM_ADVERSARY_PROVIDER", "antigravity")
    assert strategist._rc_to_reason(1) == "spawn_fast_fail"
    assert strategist._rc_to_reason(1, "adversary") \
        == "unclassified_spawn_failure"
    assert adversary._rc_reason(1) == "unclassified_spawn_failure"


def test_spawn_failure_names_why_an_rc_taught_us_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.pipeline import _spawn_failure
    monkeypatch.setenv("ASTERISM_FORMALIZER_PROVIDER", "antigravity")
    reason, detail = _spawn_failure(7, tmp_path, 900.0, kind="formalizer")
    assert reason == "unclassified_spawn_failure"
    assert "UNINFORMATIVE" in detail and "antigravity" in detail


def test_spawn_failure_on_an_undeclared_provider_degrades_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The `undeclared` ruling, in the one place that owns it: the goal
    is not charged AND the operator is told to go measure the backend.
    Warning-only would let the unknown masquerade; refusing to dispatch
    would make adding a backend a two-step landing whose first step is
    a dead framework."""
    from Tooling.pipeline import _spawn_failure
    monkeypatch.setenv("ASTERISM_FORMALIZER_PROVIDER", "codex")
    reason, detail = _spawn_failure(7, tmp_path, 900.0, kind="formalizer")
    assert reason == "unclassified_spawn_failure"
    assert "declared no rc contract" in detail
    assert "[capabilities]" in capsys.readouterr().out
    # …and the reason it degrades to carries the no-attempts traits.
    from Tooling.state import failures
    assert reason in failures.PROVIDER_INFRA_REASONS


def test_a_fast_fail_survives_an_uninformative_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duration evidence is not rc evidence: a process dead in under ten
    seconds never ran an agent, whatever its exit code meant."""
    from Tooling.pipeline import _spawn_failure
    monkeypatch.setenv("ASTERISM_FORMALIZER_PROVIDER", "antigravity")
    reason, _ = _spawn_failure(1, tmp_path, 0.4, kind="formalizer")
    assert reason == "spawn_fast_fail"


# ---------------------------------------------------------------------
# 5. Consumer — the retry helper stops claiming a detector verdict it
#    never obtained
# ---------------------------------------------------------------------

def test_timeout_on_a_streamless_provider_reports_no_detector(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """agy writes `_parser_state.json` too (usage accounting only), so
    the old file-presence check printed `[detector verdict: active
    state=— last_stop_reason=—]` about a detector that has never
    existed for this provider. The verdict now follows the
    declaration."""
    from Tooling.pipeline import PipelineResult
    from Tooling.pipeline._retry import run_with_session_retries
    from Tooling.llm.base import SpawnRC
    from tests.test_pipeline_retry_helper import (
        _seed_goal, _seed_pipeline_row,
    )

    monkeypatch.setenv("ASTERISM_FORMALIZER_PROVIDER", "antigravity")
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-agy-timeout", gid)
    # Exactly what an agy spawn leaves behind: usage, and no state.
    (tmp_path / "_parser_state.json").write_text(
        '{"usage": {"turns": 1, "input_tokens": 5}}', encoding="utf-8")

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-agy-timeout",
        budget_threshold=3, shelve_threshold=8, attempts_dir=tmp_path,
        spawn_fn=lambda _ctx: SpawnRC.TIMEOUT,
        parse_fn=lambda: PipelineResult(
            outcome="failed", failure_reason="parse_proposal_fail"),
        postmortem_fn=lambda _sid: None,
        kind="formalizer",
    )
    assert r.outcome == "exhausted"
    assert "detector verdict: none" in (r.failure_detail or "")
    assert "no stream events" in (r.failure_detail or "")
    assert "detector verdict: active" not in (r.failure_detail or "")


def test_timeout_on_a_streaming_provider_still_reports_the_detector(
    conn: sqlite3.Connection, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from Tooling.pipeline import PipelineResult
    from Tooling.pipeline._retry import run_with_session_retries
    from Tooling.llm.base import SpawnRC
    from tests.test_pipeline_retry_helper import (
        _seed_goal, _seed_pipeline_row,
    )

    monkeypatch.setenv("ASTERISM_FORMALIZER_PROVIDER", "claude")
    gid = _seed_goal(conn, attempts=0)
    _seed_pipeline_row(conn, "pid-claude-timeout", gid)
    (tmp_path / "_parser_state.json").write_text(
        '{"state": "streaming", "last_stop_reason": null, '
        '"is_thinking_trap": false}', encoding="utf-8")

    r = run_with_session_retries(
        conn=conn, goal_id=gid, pipeline_id="pid-claude-timeout",
        budget_threshold=3, shelve_threshold=8, attempts_dir=tmp_path,
        spawn_fn=lambda _ctx: SpawnRC.TIMEOUT,
        parse_fn=lambda: PipelineResult(
            outcome="failed", failure_reason="parse_proposal_fail"),
        postmortem_fn=lambda _sid: None,
        kind="formalizer",
    )
    assert "detector verdict: active" in (r.failure_detail or "")


# ---------------------------------------------------------------------
# The permission renderer may only grant what the provider honours
# (2026-08-10 owner call)
# ---------------------------------------------------------------------

def _rendered_agy_actions(kind: str = "allow"):
    """The action names `_spawn_permissions` actually emits, per side."""
    import re
    from pathlib import Path
    from types import SimpleNamespace
    from Tooling.llm import antigravity_cli as agy
    spec = SimpleNamespace(
        write_roots=(Path("D:/Asterism/.attempts/pid"),),
        mcp_config_path=None, read_deny_roots=())
    rendered = agy._spawn_permissions(spec, Path("D:/Asterism"))
    rules = rendered["permissions"][kind]
    return {re.match(r"([a-z_]+)\(", r).group(1) for r in rules}


def test_every_granted_action_is_one_agy_actually_honours() -> None:
    """The trap this exists for: someone later tries to NARROW an
    unenforceable action by writing an allow rule — "allow only
    arxiv.org" for `read_url` — and gets UNRESTRICTED fetching on agy
    instead of narrowed fetching, silently. For a benchmark an ungated
    outbound fetch is a validity problem (a route to a published
    solution) before it is a security one.

    Static, not a runtime gate: this state can only be created by
    editing the permission renderer, and a code edit is what a test is
    for. A runtime check would add a production failure mode for a
    condition production cannot reach on its own."""
    from Tooling.llm import capabilities as caps
    honoured = caps.capabilities_for("antigravity").allow_honoured_actions
    granted = _rendered_agy_actions("allow")
    assert granted, "renderer emitted no allow rules — fixture drifted"
    unenforceable = granted - honoured
    assert not unenforceable, (
        f"agy does not honour `allow` for {sorted(unenforceable)}; granting "
        f"there is either a no-op or (for read_url) silently permissive. "
        f"Honoured: {sorted(honoured)}")


def test_agy_spawn_can_still_read_the_workspace() -> None:
    """Reads are DEFAULT-DENY on agy (re-measured 2026-08-10), so the
    workspace allow is load-bearing, not decorative: with no `read_file`
    rule at all a spawn cannot open a single file — and it is never told.
    agy answers `status: SUCCESS` with an empty response and logs the
    denial only to its own file, so a blinded formalizer reads exactly
    like a lazy one. That is what got the rule deleted once."""
    from pathlib import Path
    from types import SimpleNamespace
    from Tooling.llm import antigravity_cli as agy
    spec = SimpleNamespace(write_roots=(Path("D:/Asterism/.attempts/pid"),),
                           mcp_config_path=None, read_deny_roots=())
    ws = Path("D:/Asterism")
    allow = agy._spawn_permissions(spec, ws)["permissions"]["allow"]
    assert f"read_file({ws})" in allow, (
        f"no read_file allow for the workspace — every agy spawn is blind "
        f"and silent about it. Rendered: {allow}")


def test_read_url_stays_denied_not_narrowed() -> None:
    """`read_url` is absent from the honoured set on purpose, so the ONLY
    control is deny. Pin the deny: it is a deliberate ruling (an ungated
    fetch reaches published solutions), not an incidental default."""
    denied = _rendered_agy_actions("deny")
    assert "read_url" in denied
    assert "command" in denied      # the compute channel, same ruling


def test_undeclared_provider_grants_nothing() -> None:
    """A backend that declared nothing must not be handed a capability
    the framework merely ASSUMES will be enforced — the empty default is
    load-bearing, not cosmetic."""
    from Tooling.llm import capabilities as caps
    assert caps.capabilities_for("codex-not-yet-measured"
                                 ).allow_honoured_actions == frozenset()


def test_headline_and_per_action_do_not_contradict() -> None:
    """The coarse word and the per-action set describe the same reality;
    a `hard` provider honours everything, `not_applicable` honours
    nothing. Catches an edit that updates one and forgets the other."""
    from Tooling.llm import capabilities as caps
    for cap in caps.CAPABILITIES.values():
        if cap.enforcement_strength == caps.ENFORCEMENT_HARD:
            assert cap.allow_honoured_actions == caps.ALLOW_HONOURED_ALL, cap.name
        elif cap.enforcement_strength in (caps.ENFORCEMENT_NOT_APPLICABLE,
                                          caps.ENFORCEMENT_UNDECLARED):
            assert cap.allow_honoured_actions == frozenset(), cap.name
        elif cap.enforcement_strength == caps.ENFORCEMENT_DENY_ONLY:
            # The whole point: some actions honoured, not all.
            assert cap.allow_honoured_actions, cap.name
            assert cap.allow_honoured_actions != caps.ALLOW_HONOURED_ALL, cap.name
