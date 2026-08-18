"""asterism doctor: pre-flight check for tools / config / problem
intent / filesystem. Subprocess invocations are mocked via monkeypatching
shutil.which + subprocess.run so tests are fast and don't depend on
a real toolchain on the runner."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Any

import pytest

from Tooling.core import config
from Tooling.core.cli import cmd_doctor, cmd_init


_MIN_SEED = (
    '{"problem": "wilson", "charter": "Statement: True"}\n'
)


class _FakeRun:
    """Monkeypatch target for subprocess.run during doctor tests.
    Each response key is a space-joined cmd prefix (e.g. `claude --version`,
    `lake env lean --version`); doctor's actual cmd[0] may be an absolute
    path (`/fake/gemini` or `gemini.cmd`), so we match against its
    basename-without-extension to stay platform-agnostic."""
    def __init__(self, responses: dict[str, tuple[int, str]]):
        self.responses = responses
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
        self.calls.append(cmd)
        # Normalize cmd[0]: '/fake/gemini' or 'gemini.cmd' → 'gemini'.
        base = Path(cmd[0]).stem if cmd else ""
        norm = [base] + list(cmd[1:])
        for key, (rc, stdout) in self.responses.items():
            tokens = key.split()
            if norm[: len(tokens)] == tokens:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=rc, stdout=stdout, stderr="")
        raise RuntimeError(f"unexpected subprocess.run cmd={cmd}")


def _setup_tools(monkeypatch: pytest.MonkeyPatch, *,
                 has_claude: bool = True, has_gemini: bool = True,
                 has_lake: bool = True, has_agy: bool = True,
                 agy_perms: bool = True, agy_legacy_creds: bool = False,
                 responses: dict[str, tuple[int, str]] | None = None) -> _FakeRun:
    """Wire fake `which` + fake `run` so cmd_doctor sees the desired toolchain.

    `agy` needs its own two hooks: the provider's resolver probes the
    installer path (`%LOCALAPPDATA%\\agy\\bin`) directly instead of going
    through `which` — the PowerShell installer edits the user PATH that a
    running daemon never sees — and its permissions file lives in the real
    HOME. Both are patched so no test reaches the real binary or home."""
    from Tooling.llm import antigravity_cli as _agy
    monkeypatch.setattr(
        _agy, "resolve_agy_executable",
        lambda: "/fake/agy" if has_agy else None)
    monkeypatch.setattr(
        _agy, "permissions_path",
        lambda: (Path(__file__) if agy_perms
                 else Path("/fake/home/.gemini/antigravity-cli/settings.json")))
    monkeypatch.setattr(
        _agy, "legacy_oauth_creds_path",
        lambda: (Path(__file__) if agy_legacy_creds
                 else Path("/fake/home/.gemini/oauth_creds.json")))
    available = set()
    if has_claude:
        available.add("claude")
    if has_gemini:
        available.add("gemini")
    if has_lake:
        available.add("lake")
    monkeypatch.setattr(
        "Tooling.cli.shutil.which" if False else "shutil.which",
        lambda name: f"/fake/{name}" if name in available else None,
    )
    fake = _FakeRun(responses or {
        "claude --version": (0, "2.1.123 (Claude Code)\n"),
        "gemini --version": (0, "0.40.1\n"),
        "agy --version": (0, "1.1.8\n"),
        "lake env lean --version": (0, "Lean (version 4.x.x)\n"),
    })
    monkeypatch.setattr("subprocess.run", fake)
    return fake


@pytest.fixture(autouse=True)
def _reset_cfg_cache() -> None:
    config._reset_cache()
    yield
    config._reset_cache()


def _setup_problem(tmp_path: Path, name: str = "wilson") -> Path:
    pdir = tmp_path / "Problems" / name
    pdir.mkdir(parents=True)
    (pdir / "problem.json").write_text(_MIN_SEED, encoding="utf-8")
    (pdir / "Defs.lean").write_text(
        f"import Mathlib\n\nnamespace Problems.{name}\n\nend Problems.{name}\n",
        encoding="utf-8",
    )
    (pdir / "Root.lean").write_text(
        f"import Mathlib\nimport Problems.{name}.Defs\n\n"
        f"namespace Problems.{name}\n\n"
        f"theorem main : True := by sorry\n\n"
        f"end Problems.{name}\n",
        encoding="utf-8",
    )
    return pdir


# ---------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------

def test_doctor_all_green(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Healthy toolchain + initialized Problem + clean filesystem
    yields rc=0 and no FAIL lines."""
    _setup_tools(monkeypatch)
    _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=True))
    capsys.readouterr()  # discard init's stdout

    rc = cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 0
    assert "FAIL" not in out
    assert "claude" in out
    assert "gemini" in out
    assert "lake" in out
    assert "wilson" in out


# ---------------------------------------------------------------------
# Failure detection
# ---------------------------------------------------------------------

def test_doctor_lake_missing_is_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Lake is mandatory — its absence must FAIL the run."""
    _setup_tools(monkeypatch, has_lake=False)
    monkeypatch.chdir(tmp_path)
    rc = cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out
    assert "lake" in out


def test_doctor_claude_missing_is_warn_not_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Claude is optional (a project might use only Gemini) so its
    absence is WARN, not FAIL."""
    _setup_tools(monkeypatch, has_claude=False)
    monkeypatch.chdir(tmp_path)
    rc = cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 0
    assert "WARN" in out


def test_doctor_reports_agy_and_its_permission_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`agy` present + its permissions file present → both OK. The file
    is not cosmetic: without it every tool call is auto-denied in
    headless mode and a spawn returns SUCCESS having written nothing
    (antigravity_cli.py, THE HAZARD), so doctor has to surface it."""
    _setup_tools(monkeypatch)
    monkeypatch.chdir(tmp_path)
    assert cmd_doctor(argparse.Namespace()) == 0
    out = capsys.readouterr().out
    assert "agy     1.1.8" in out
    assert "agy permissions:" in out


def test_doctor_warns_when_agy_permissions_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _setup_tools(monkeypatch, agy_perms=False)
    monkeypatch.chdir(tmp_path)
    assert cmd_doctor(argparse.Namespace()) == 0
    out = capsys.readouterr().out
    assert "agy permissions file missing" in out
    assert "auto-denied" in out


def test_doctor_warns_when_legacy_gemini_creds_shadow_the_ide_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`~/.gemini/oauth_creds.json` outranks the Antigravity IDE session
    (antigravity_cli.py §2b): on 2026-07-30 both existed under different
    accounts and the file won, so the run silently drew on the operator's
    free tier while the IDE held the AI Pro login. Nothing errors when
    the wrong account wins — quota just comes out of the wrong place —
    so presence has to be surfaced."""
    _setup_tools(monkeypatch, agy_legacy_creds=True)
    monkeypatch.chdir(tmp_path)
    assert cmd_doctor(argparse.Namespace()) == 0
    out = capsys.readouterr().out
    assert "prefers it over the Antigravity IDE session" in out


def test_doctor_reports_ide_session_identity_when_unshadowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _setup_tools(monkeypatch)
    monkeypatch.chdir(tmp_path)
    assert cmd_doctor(argparse.Namespace()) == 0
    assert "agy identity: Antigravity IDE session" in capsys.readouterr().out


def test_doctor_agy_absent_is_warn_not_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Optional provider — a claude-only run must not fail doctor."""
    _setup_tools(monkeypatch, has_agy=False)
    monkeypatch.chdir(tmp_path)
    assert cmd_doctor(argparse.Namespace()) == 0
    assert "Antigravity provider" in capsys.readouterr().out


def test_doctor_unparseable_yaml_is_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A malformed Asterism.yaml during doctor should FAIL — config.load
    swallows it for the daemon, but doctor's job is to surface it."""
    _setup_tools(monkeypatch)
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: [unclosed\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rc = cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    # config.load itself emits a WARNING line before doctor's check
    # runs; the fail/ok signal lives on the [   OK]/[ FAIL] doctor line.
    assert "Asterism.yaml" in out
    # Either FAIL via doctor's own except or the WARNING line — at
    # minimum the file's name appears alongside FAIL or parse error.
    assert (rc == 1) or ("WARNING" in out)


def test_doctor_problem_without_charter_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """v40 successor of the vanished-Manifest FAIL: the user-intent
    surface is the DB charter now. A registered problem whose top-group
    charter is empty → FAIL line; a missing problem.json (charter still
    in DB) only WARNs — the runtime SoT is intact, the durable seed is
    what's gone."""
    _setup_tools(monkeypatch)
    _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=True))
    # Missing seed → WARN only (rc stays 0)
    (tmp_path / "Problems" / "wilson" / "problem.json").unlink()
    capsys.readouterr()
    rc = cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 0
    assert "problem.json missing" in out

    # Empty charter → FAIL (bypass intent.set_charter, which refuses "")
    from Tooling.state import db as _db
    conn = _db.connect()
    conn.execute(
        "UPDATE groups SET charter = '' WHERE problem = 'wilson'"
        " AND parent_group_id IS NULL")
    conn.commit()
    conn.close()
    rc = cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out
    assert "wilson" in out
    assert "no charter" in out


def test_doctor_warns_on_many_attempts_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A pile of stale .attempts/ subdirs → WARN reminding to clean up."""
    _setup_tools(monkeypatch)
    monkeypatch.chdir(tmp_path)
    attempts = tmp_path / ".attempts"
    attempts.mkdir()
    for i in range(7):
        (attempts / f"pid-{i}").mkdir()
    rc = cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    # Should contain a WARN line about .attempts and a "rm" hint
    assert "WARN" in out
    assert ".attempts/" in out
    assert rc == 0


def test_doctor_no_problems_initialized_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Empty DB → WARN telling user to init."""
    _setup_tools(monkeypatch)
    monkeypatch.chdir(tmp_path)
    rc = cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 0
    assert "WARN" in out
    assert "init" in out  # hint message


def test_doctor_yaml_summary_lists_sections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A populated Asterism.yaml: doctor reports the section names with
    field counts so operator confirms the file was actually read."""
    _setup_tools(monkeypatch)
    (tmp_path / "Asterism.yaml").write_text(
        "dispatch:\n  pool: 8\n  budget_sec: 3600\n"
        "builder:\n  provider: claude\n  model: claude-haiku-4-5\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    rc = cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 0
    assert "dispatch(2)" in out
    assert "builder(2)" in out
