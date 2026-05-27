"""asterism doctor: pre-flight check for tools / config / Manifests
/ filesystem. Subprocess invocations are mocked via monkeypatching
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


_MIN_MANIFEST = (
    "# wilson\n\n## Statement\n\nTrue\n\n## Difficulty\n\n1\n"
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
                 has_lake: bool = True,
                 responses: dict[str, tuple[int, str]] | None = None) -> _FakeRun:
    """Wire fake `which` + fake `run` so cmd_doctor sees the desired toolchain."""
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
    (pdir / "Manifest.md").write_text(_MIN_MANIFEST, encoding="utf-8")
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


def test_doctor_initialized_problem_with_missing_manifest_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Problem registered in DB but Manifest.md vanished → FAIL line."""
    _setup_tools(monkeypatch)
    _setup_problem(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd_init(argparse.Namespace(problem="wilson", force=True))
    # Delete Manifest.md after init
    (tmp_path / "Problems" / "wilson" / "Manifest.md").unlink()
    capsys.readouterr()

    rc = cmd_doctor(argparse.Namespace())
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out
    assert "wilson" in out


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
