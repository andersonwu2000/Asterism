"""The drift guard: version compare + behaviour snapshot.

Version equality cannot catch "same CLI version, changed server-side
wording", and EVERY quota / misconfig detector this project owns is a
substring match against vendor prose. When one stops matching, nothing
errors: the quota refusal reads as an ordinary failure, the backoff
probes a three-hour wall, and the first symptom is a run that got
nowhere. So the guard also captures a small behaviour snapshot from a
free probe and diffs it.

Everything here is a WARNING. A guard that can stop a run is a new way
for the run to die.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from Tooling.llm import capabilities as caps
from Tooling.llm import drift_guard


@pytest.fixture(autouse=True)
def _clean_warning_state():
    caps._reset_warned_for_tests()
    yield
    caps._reset_warned_for_tests()


def _fake_cli(monkeypatch: pytest.MonkeyPatch, *, version: str,
              probe_out: str, probe_rc: int = 1) -> None:
    """Stand in for a provider CLI: `--version` and the free probe."""
    monkeypatch.setattr(drift_guard, "resolve_executable",
                        lambda _p: "fake.exe")

    def _run(argv, cwd):
        if argv[1:2] == ["--version"]:
            return 0, version
        return probe_rc, probe_out

    monkeypatch.setattr(drift_guard, "_run", _run)


_AGY_OK = (
    'Error: invalid model selection (--model "<slug>" --effort ""): '
    'model <slug> is not recognized as a known model or custom model '
    'in settings\n'
    "Available models:\n"
    "  Gemini 3.6 Flash (High)\n"
    "  Gemini 3.1 Pro (High)\n"
)


def test_first_run_records_a_baseline_without_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_cli(monkeypatch, version="1.1.11", probe_out=_AGY_OK)
    assert drift_guard.check(tmp_path, ("antigravity",)) == []
    stored = json.loads(
        (tmp_path / drift_guard.SNAPSHOT_REL).read_text(encoding="utf-8"))
    assert stored["antigravity"]["version"] == "1.1.11"
    assert stored["antigravity"]["probe"]["marker_ok"] is True
    assert "Available models:" in stored["antigravity"]["probe"]["signature"]


def test_version_drift_warns_and_names_the_marker_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Warns, never blocks: both vendor CLIs self-update, and refusing
    to start would convert a paperwork gap into an outage. The message
    has to say WHICH tables were validated at the old version — that is
    the whole reason `tested_version` is bound to `marker_tables`."""
    _fake_cli(monkeypatch, version="9.9.9", probe_out=_AGY_OK)
    warnings = drift_guard.check(tmp_path, ("antigravity",))
    assert len(warnings) == 1
    w = warnings[0]
    assert "9.9.9" in w and caps.CAPABILITIES["antigravity"].tested_version in w
    assert "_QUOTA_MARKERS" in w and "_MISCONFIG_MARKERS" in w


def test_a_reworded_error_at_the_same_version_is_caught(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The case version equality can never see."""
    version = caps.CAPABILITIES["antigravity"].tested_version
    _fake_cli(monkeypatch, version=version, probe_out=_AGY_OK)
    assert drift_guard.check(tmp_path, ("antigravity",)) == []

    reworded = _AGY_OK.replace("  Gemini 3.1 Pro (High)\n", "")
    _fake_cli(monkeypatch, version=version, probe_out=reworded)
    warnings = drift_guard.check(tmp_path, ("antigravity",))
    assert any("behaviour snapshot CHANGED" in w for w in warnings)
    assert any("Gemini 3.1 Pro (High)" in w for w in warnings)


def test_a_marker_that_stopped_matching_is_the_loudest_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead detector looks exactly like 'this never happens' — which
    is why the warning has to name the table it kills."""
    version = caps.CAPABILITIES["antigravity"].tested_version
    _fake_cli(monkeypatch, version=version,
              probe_out="Error: unknown model, sorry\n")
    warnings = drift_guard.check(tmp_path, ("antigravity",))
    assert any("DEAD SILENT" in w for w in warnings)
    assert any("_MISCONFIG_MARKERS" in w for w in warnings)


def test_the_claude_probe_exercises_the_stale_session_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The probe is not decorative: its `must_contain` IS the sentinel
    the in-pipeline retry helper needs to re-mint a session without
    burning budget, so the guard's green light means that specific
    detector still works."""
    from Tooling.llm import claude_cli
    probe = drift_guard.PROBES["claude"]
    assert probe.must_contain == claude_cli._STALE_SESSION_MARKER
    _fake_cli(monkeypatch,
              version=caps.CAPABILITIES["claude"].tested_version,
              probe_out="No conversation found with session ID: <uuid>\n")
    assert drift_guard.check(tmp_path, ("claude",)) == []


def test_the_agy_probe_exercises_a_real_misconfig_marker() -> None:
    from Tooling.llm import antigravity_cli as agy
    probe = drift_guard.PROBES["antigravity"]
    assert probe.must_contain in agy._MISCONFIG_MARKERS


def test_a_missing_cli_is_silent_not_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`asterism doctor` already says a CLI is absent; the drift guard
    repeating it would train the operator to ignore this channel."""
    monkeypatch.setattr(drift_guard, "resolve_executable", lambda _p: None)
    assert drift_guard.check(tmp_path, ("claude", "antigravity")) == []


def test_an_undeclared_provider_is_skipped_and_warned_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(drift_guard, "resolve_executable",
                        lambda _p: "fake.exe")
    assert drift_guard.check(tmp_path, ("codex",)) == []
    assert "[capabilities]" in capsys.readouterr().out


def test_the_guard_never_raises_out_of_run_and_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*_a, **_kw):
        raise RuntimeError("probe exploded")

    monkeypatch.setattr(drift_guard, "check", _boom)
    assert drift_guard.run_and_report(tmp_path) == []


def test_start_background_can_be_switched_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A test harness (or a box with no CLIs) must be able to keep the
    daemon from shelling out at all."""
    called: list = []
    monkeypatch.setattr(drift_guard, "run_and_report",
                        lambda ws: called.append(ws))
    monkeypatch.setenv("ASTERISM_SKIP_PROVIDER_DRIFT_CHECK", "1")
    drift_guard.start_background(tmp_path).join(timeout=5)
    assert called == []
    monkeypatch.delenv("ASTERISM_SKIP_PROVIDER_DRIFT_CHECK")
    drift_guard.start_background(tmp_path).join(timeout=5)
    assert called == [tmp_path]


# ---------------------------------------------------------------------
# Live probes — free (no API call, no quota), skipped when absent
# ---------------------------------------------------------------------

@pytest.mark.free_cli_probe
@pytest.mark.parametrize("provider", ["claude", "antigravity"])
def test_the_installed_cli_matches_its_declaration_right_now(
    provider: str, tmp_path: Path,
) -> None:
    """The real thing, against the real CLI. `--version` and an invalid
    `--model` / a nonexistent `--resume` id are answered locally, so
    this costs nothing and works with the subscription exhausted.

    A FAILURE here is not a broken test — it is the guard doing its job
    from inside CI: update `capabilities.tested_version` (and re-verify
    the marker tables) in the same change that acknowledges the new CLI.
    """
    if drift_guard.resolve_executable(provider) is None:
        pytest.skip(f"{provider} CLI not installed on this machine")
    snap = drift_guard.behaviour_snapshot(provider, workspace=tmp_path)
    assert snap is not None
    assert snap["marker_ok"], (
        f"{provider}: {drift_guard.PROBES[provider].marker_source} no "
        f"longer matches the CLI's own output — {snap}")
    assert drift_guard.installed_version(provider) == \
        caps.CAPABILITIES[provider].tested_version
