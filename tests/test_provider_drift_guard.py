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


#: Verbatim from codex v0.147.0, 2026-08-13 — the config-load failure
#: the probe provokes. `<value>` is what the redaction leaves behind.
_CODEX_OK = (
    "Error loading config.toml: unknown variant `<value>`, expected one "
    "of `read-only`, `workspace-write`, `danger-full-access`\n"
    "in `sandbox_mode`\n"
)


def test_the_codex_probe_exercises_a_real_misconfig_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two markers in one output, and the second is the one pinned:
    "unknown variant" is `_MISCONFIG_MARKERS`' enum-shaped entry, and
    "error loading config.toml" rides along in the signature. The probe
    argv is load-bearing in a way the other providers' are not — the
    obvious variants (unknown top-level field, invalid `--model`) were
    measured on 2026-08-13 to reach the real API — so this test also
    pins the argv shape."""
    from Tooling.llm import codex_cli
    probe = drift_guard.PROBES["codex"]
    assert probe.must_contain in codex_cli._MISCONFIG_MARKERS
    assert "error loading config.toml" in codex_cli._MISCONFIG_MARKERS
    # The one client-side-fatal shape: an illegal ENUM value via `-c`.
    assert probe.argv_tail[0] == "exec"
    assert any(a.startswith('sandbox_mode="') for a in probe.argv_tail)
    assert "--model" not in probe.argv_tail
    _fake_cli(monkeypatch,
              version=caps.CAPABILITIES["codex"].tested_version,
              probe_out=_CODEX_OK)
    assert drift_guard.check(tmp_path, ("codex",)) == []
    stored = json.loads(
        (tmp_path / drift_guard.SNAPSHOT_REL).read_text(encoding="utf-8"))
    assert stored["codex"]["probe"]["marker_ok"] is True
    # Both marker phrases survive into the stored signature, so a
    # rewording of EITHER shows up as a snapshot diff.
    sig = "\n".join(stored["codex"]["probe"]["signature"]).lower()
    assert "unknown variant" in sig
    assert "error loading config.toml" in sig


def test_a_dead_codex_marker_names_its_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rot direction: codex rewords the config error, the misconfig
    classifier goes silent, and the warning must say WHICH table died."""
    _fake_cli(monkeypatch,
              version=caps.CAPABILITIES["codex"].tested_version,
              probe_out="error: configuration file is malformed\n")
    warnings = drift_guard.check(tmp_path, ("codex",))
    assert any("DEAD SILENT" in w for w in warnings)
    assert any("codex_cli._MISCONFIG_MARKERS" in w for w in warnings)


# ---------------------------------------------------------------------
# Coverage: a table nobody watches must SAY so (2026-08-13)
# ---------------------------------------------------------------------
#
# The guard's docstring claimed it watched every quota and misconfig
# detector we own. `PROBES` exercises one table per provider; seven are
# declared. `claude_cli`'s quota prose went unwatched from roughly
# 2026-07-03 to 2026-08-13 — and the guard reported GREEN throughout,
# for the other table. Silence and coverage were indistinguishable.


def test_every_declared_marker_table_declares_its_coverage() -> None:
    """The teeth. A new marker table must classify itself as live-probe,
    corpus, or unverified — there is no default, so the next one cannot
    arrive unwatched AND unremarked the way five of these did."""
    coverage = drift_guard.marker_coverage()
    assert coverage, "no marker tables declared at all — did the schema move?"
    unclassified = sorted(k for k, v in coverage.items()
                          if v == "UNCLASSIFIED")
    assert not unclassified, (
        "these marker tables are watched by nothing and say nothing "
        "about it — add a probe, pin a captured sample in "
        "COVERED_BY_CORPUS, or state the reason in UNVERIFIED:\n  "
        + "\n  ".join(unclassified))


def test_a_live_probe_claim_names_a_real_probe() -> None:
    """`live-probe` is the only kind that asserts something about the
    CLI as installed right now, so it must not be claimable by writing
    the words: it is derived from `PROBES`, and every probe's
    `marker_source` must be a table someone actually declared."""
    declared = {d for c in caps.CAPABILITIES.values()
                for d in c.marker_tables}
    for name, probe in drift_guard.PROBES.items():
        assert probe.marker_source in declared, (
            f"{name}'s probe exercises {probe.marker_source!r}, which no "
            f"capability entry declares — the probe and the declaration "
            f"have drifted apart")


def test_the_three_coverage_kinds_are_disjoint() -> None:
    """A table in two buckets means two people believe someone else is
    watching it."""
    by_probe = {p.marker_source for p in drift_guard.PROBES.values()}
    corpus = set(drift_guard.COVERED_BY_CORPUS)
    unverified = set(drift_guard.UNVERIFIED)
    assert not (by_probe & corpus)
    assert not (by_probe & unverified)
    assert not (corpus & unverified)


def test_every_unverified_entry_gives_a_reason() -> None:
    """"Unverified" without a reason is just silence with extra steps —
    and the reason is what tells the next reader whether the gap is in
    the world (a refusal costs real quota to trigger) or in us (nobody
    wired the probe yet)."""
    for dotted, why in drift_guard.UNVERIFIED.items():
        assert len(why.strip()) > 40, f"{dotted}: reason too thin"


def test_a_corpus_claim_points_at_a_test_that_exists() -> None:
    from pathlib import Path as _P
    root = _P(__file__).resolve().parents[1]
    for dotted, where in drift_guard.COVERED_BY_CORPUS.items():
        rel = where.split(" ", 1)[0]
        assert (root / rel).exists(), (
            f"{dotted} claims coverage by {rel!r}, which does not exist")


# ---------------------------------------------------------------------
# "Did not answer" is not "answered wrong" (2026-08-14)
# ---------------------------------------------------------------------


def _mute_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """A CLI that is installed but never answers the probe."""
    import subprocess

    monkeypatch.setattr(drift_guard, "resolve_executable",
                        lambda _p: "fake.exe")

    def _run(argv, cwd):
        if argv[1:2] == ["--version"]:
            return 0, caps.CAPABILITIES["antigravity"].tested_version
        raise subprocess.TimeoutExpired(argv, 20)

    monkeypatch.setattr(drift_guard, "_run", _run)


def test_an_unanswered_probe_is_unmeasured_not_a_dead_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The distinction that cost a red suite. A probe that times out
    used to report `marker_ok: False`, which reads as "the vendor
    reworded its error and a detector just went silent" — the loudest
    thing this guard can say, produced by a busy box."""
    _mute_cli(monkeypatch)
    snap = drift_guard.behaviour_snapshot("antigravity", workspace=tmp_path)
    assert snap is not None and snap["marker_ok"] is None
    assert "TimeoutExpired" in snap["error"]
    warnings = drift_guard.check(tmp_path, ("antigravity",))
    assert any("could not be run" in w for w in warnings)
    assert not any("DEAD SILENT" in w for w in warnings)


def test_an_unanswered_probe_does_not_fake_a_snapshot_diff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second false alarm hiding behind the first: an unmeasured
    probe carries an EMPTY signature, so the diff against the last real
    one would announce that the vendor's wording moved. The stored
    snapshot must survive a failed measurement untouched — otherwise
    the NEXT run diffs against the empty one and lies twice."""
    _fake_cli(monkeypatch, version=caps.CAPABILITIES["antigravity"]
              .tested_version, probe_out=_AGY_OK)
    assert drift_guard.check(tmp_path, ("antigravity",)) == []
    good = json.loads((tmp_path / drift_guard.SNAPSHOT_REL)
                      .read_text(encoding="utf-8"))["antigravity"]["probe"]

    _mute_cli(monkeypatch)
    warnings = drift_guard.check(tmp_path, ("antigravity",))
    assert not any("CHANGED" in w for w in warnings)
    kept = json.loads((tmp_path / drift_guard.SNAPSHOT_REL)
                      .read_text(encoding="utf-8"))["antigravity"]["probe"]
    assert kept == good


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
    assert drift_guard.check(tmp_path, ("no-such-backend",)) == []
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
@pytest.mark.parametrize("provider", ["claude", "antigravity", "codex"])
def test_the_installed_cli_matches_its_declaration_right_now(
    provider: str, tmp_path: Path,
) -> None:
    """The real thing, against the real CLI. A nonexistent `--resume` id
    (claude), an invalid `--model` (agy) and an illegal `sandbox_mode`
    enum value (codex) are all answered locally, so this costs nothing
    and works with the subscription exhausted.

    A FAILURE here is not a broken test — it is the guard doing its job:
    re-measure what the record vouches for, then update
    `capabilities.tested_version` in the same change.

    Two grains, on purpose (2026-08-12). The marker check is EXACT and
    live: it re-measures on every run, so it costs nothing to keep
    strict and it is the only thing that catches a `tested_version`
    bumped without re-measuring (the 1.1.8 → 1.1.11 lie of 08-09). The
    version check is per minor SERIES: claude and agy ship patches every
    few days, exact equality left this red for a week at a time, and a
    permanently red guard is one nobody reads.

    What it must NOT do is go red for weather. This shells out to a real
    vendor CLI, so under the full suite it competes with every other
    subprocess and the probe sometimes never answers — observed once on
    2026-08-13, green alone and green on the next full run. That is not
    a measurement of the codebase, and letting it fail turns "the suite
    is green" into a dice roll (the #200 lesson, one day old at the
    time). An UNANSWERED probe skips; a probe that answers and
    contradicts the record still fails, which is the whole point.
    """
    if drift_guard.resolve_executable(provider) is None:
        pytest.skip(f"{provider} CLI not installed on this machine")
    snap = drift_guard.behaviour_snapshot(provider, workspace=tmp_path)
    assert snap is not None
    if snap["marker_ok"] is None:
        pytest.skip(f"{provider} CLI did not answer its free probe "
                    f"({snap.get('error')}) — nothing measured")
    assert snap["marker_ok"], (
        f"{provider}: {drift_guard.PROBES[provider].marker_source} no "
        f"longer matches the CLI's own output — {snap}")
    installed = drift_guard.installed_version(provider)
    if installed is None:
        pytest.skip(f"{provider} CLI did not answer `--version`")
    declared = caps.CAPABILITIES[provider].tested_version
    assert drift_guard.same_series(installed, declared), (
        f"{provider}: installed {installed}, record vouched at {declared} "
        f"— a different minor series, so re-measure the rc contract, the "
        f"permission semantics and the stream shape before bumping it")


# ─── the grain the version pin vouches at (2026-08-12) ───

def test_a_patch_bump_is_the_same_series():
    """Both of today's reds were patch-level — claude 2.1.224→2.1.226,
    agy 1.1.11→1.1.12 — and neither moved a fact the record vouches
    for."""
    assert drift_guard.same_series("2.1.226", "2.1.224")
    assert drift_guard.same_series("1.1.12", "1.1.11")


def test_a_minor_bump_still_fires():
    """Where the expensive facts actually move."""
    assert not drift_guard.same_series("2.2.0", "2.1.224")
    assert not drift_guard.same_series("2.1.224", "3.0.1")


def test_the_series_check_cannot_catch_a_lie_inside_one_series():
    """Stated rather than hidden: 08-09's `tested_version` 1.1.8 → 1.1.11
    was a bare `--version` bump while the facts stayed 1.1.8's, and this
    comparison waves it through — exactly as exact-equality did, since
    the field had already been edited. The guard for that is the live
    marker probe, which is why THAT one stays exact."""
    assert drift_guard.same_series("1.1.11", "1.1.8")


def test_missing_versions_never_pass_silently():
    for a, b in (("2.1.226", None), (None, "2.1.226"), (None, None)):
        assert not drift_guard.same_series(a, b)
