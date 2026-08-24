"""`installer/install.sh` — the Linux/macOS installer, extended for
Oracle ARM64 readiness (docs/internal/dev/oracle_arm64_cloud_readiness.md
P0#1 installer half + P1#6).

The script is sourceable (guarded by a BASH_SOURCE == $0 check at the
bottom) specifically so this file can exercise its pure decision
functions — architecture classification, provider selection from
Asterism.yaml, the leantar arch-mismatch detector, and the JSON seam
onto `installer/provider-info.py` — without running a real Lean/Node
install, hitting the network, or requiring a real Oracle box. No test
here invokes `main` (which would install things for real).

`bash` is Git Bash (MSYS) on this Windows dev box — the same
interpreter these scripts are meant to run under on Linux/macOS, so the
syntax and control-flow paths exercised here are the real ones.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import textwrap
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO / "installer" / "install.sh"


def _find_bash() -> "str | None":
    """Git Bash on Windows, never WSL. `shutil.which("bash")` on the
    GitHub windows runner returns System32's WSL launcher: inside WSL
    the fake-`file` PATH prepend never applies (Windows paths mount
    AFTER the Linux tree), so the distro's REAL /usr/bin/file answered
    and five leantar tests went red on paths like /opt/lean/bin
    (first windows-latest run of the installer suite, 2026-08-24)."""
    if sys.platform == "win32":
        found = shutil.which("bash")
        if found and "system32" not in found.lower():
            # Git's TOP-LEVEL bin\bash.exe is a re-exec wrapper that
            # rebuilds the environment — the fake-bin PATH prepend the
            # leantar tests rely on is gone by the time the script
            # runs, so the REAL `file` answered and five tests went
            # red (windows-latest, 2026-08-24; reproduced locally
            # against the same wrapper). The msys usr\bin\bash.exe
            # honors the caller's env verbatim — swap to it when the
            # wrapper is what PATH found.
            p = Path(found)
            if p.parent.name.lower() == "bin" \
                    and p.parent.parent.name.lower() == "git":
                msys = p.parent.parent / "usr" / "bin" / "bash.exe"
                if msys.is_file():
                    return str(msys)
            return found  # already the msys bash (usr\bin\bash.EXE)
        candidates = []
        git = shutil.which("git")
        if git:
            # git lives at <root>\cmd\git.exe or <root>\mingw64\bin\
            # git.exe — probe both plausible roots for the msys bash
            for root in Path(git).resolve().parents[1:3]:
                candidates += [root / "usr" / "bin" / "bash.exe",
                               root / "bin" / "bash.exe"]
        for pf in (r"C:\Program Files\Git",
                   r"C:\Program Files (x86)\Git"):
            candidates += [Path(pf) / "usr" / "bin" / "bash.exe",
                           Path(pf) / "bin" / "bash.exe"]
        for c in candidates:
            if c.is_file():
                return str(c)
        return None
    return shutil.which("bash")


_BASH = _find_bash()

pytestmark = pytest.mark.skipif(
    _BASH is None, reason="no Git Bash / bash on PATH")


def _run(snippet: str, *, env_extra: "dict[str, str] | None" = None,
        cwd: "Path | None" = None,
        argv: "list[str] | None" = None) -> subprocess.CompletedProcess:
    """Source install.sh in a fresh bash, then run `snippet`.

    Every test gets PY pointed at the interpreter actually running this
    suite (`sys.executable`) — the environment's bare `python3` is a
    Windows Store stub that exits 49 without running anything, which
    install.sh itself never hits on a real Linux box (step_python picks
    a real interpreter there) but this test harness must route around.
    """
    import os
    env = dict(os.environ)
    env["PY"] = sys.executable
    if env_extra:
        env.update(env_extra)
    if sys.platform == "win32" and _BASH:
        # The msys usr\bin\bash.exe honors the caller's env verbatim
        # (that is why _find_bash picks it over the re-exec wrapper) —
        # which also means nobody rebuilds PATH for it: on a machine
        # whose PATH lacks Git's usr\bin, every coreutil the script
        # touches is `command not found` (dirname/tr went 127 locally,
        # 2026-08-25; CI was green only because the runner image
        # carries usr\bin on PATH). Insert bash's own dir AFTER any
        # test-provided fake-bin prepends (they must keep shadowing)
        # and BEFORE the inherited tail (System32's find/sort must not
        # shadow the coreutils install.sh calls).
        usrbin = str(Path(_BASH).parent)
        base = os.environ.get("PATH", "")
        cur = env.get("PATH", "")
        if usrbin not in cur.split(os.pathsep):
            if base and cur.endswith(base):
                head = cur[: len(cur) - len(base)]
                env["PATH"] = head + usrbin + os.pathsep + base
            else:
                env["PATH"] = usrbin + os.pathsep + cur
    full = f'source "{_SCRIPT.as_posix()}"\n{snippet}'
    cmd = [_BASH, "-c", full, "install.sh", *(argv or [])]
    return subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8",
        errors="replace",
        env=env, cwd=str(cwd or _REPO), timeout=30,
    )


def _with_fake_bin(tmp_path: Path, name: str, body: str) -> Path:
    """Write an executable fake command `name` into a fresh dir and
    return that dir (to be prepended onto PATH)."""
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    script = bindir / name
    script.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
    script.chmod(0o755)
    return bindir


# --------------------------------------------------------------------
# syntax
# --------------------------------------------------------------------

def test_bash_syntax_ok() -> None:
    p = subprocess.run([_BASH, "-n", str(_SCRIPT)],
                       capture_output=True, text=True, timeout=15)
    assert p.returncode == 0, p.stderr


def test_sourcing_does_not_run_main(tmp_path: Path) -> None:
    """The BASH_SOURCE guard must actually work — sourcing must not
    install anything or print the step banners."""
    p = _run("echo sourced-ok")
    assert p.returncode == 0, p.stderr
    assert "sourced-ok" in p.stdout
    assert "engine installed" not in p.stdout
    assert "math library ready" not in p.stdout


# --------------------------------------------------------------------
# architecture classification (mirrors cloud_doctor.classify_host_arch
# / classify_elf_arch — kept in lockstep by these two function pairs)
# --------------------------------------------------------------------

@pytest.mark.parametrize("machine,want", [
    ("aarch64", "aarch64"),
    ("arm64", "aarch64"),
    ("AARCH64", "aarch64"),
    ("x86_64", "x86_64"),
    ("amd64", "x86_64"),
    ("riscv64", "unknown"),
    ("", "unknown"),
])
def test_classify_host_arch(machine: str, want: str) -> None:
    p = _run(f'classify_host_arch "{machine}"')
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == want


@pytest.mark.parametrize("file_output,want", [
    ("ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV)",
     "aarch64"),
    ("ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV)",
     "x86_64"),
    ("ELF 64-bit LSB executable, x86_64", "x86_64"),
    ("data", "unknown"),
])
def test_classify_elf_arch(file_output: str, want: str) -> None:
    p = _run(f'classify_elf_arch "{file_output}"')
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == want


# --------------------------------------------------------------------
# enabled_providers: Asterism.yaml -> the seat set, always +claude
# --------------------------------------------------------------------

def test_enabled_providers_defaults_to_claude_when_no_yaml(
        tmp_path: Path) -> None:
    p = _run('ROOT="$FAKE_ROOT"\nenabled_providers',
            env_extra={"FAKE_ROOT": str(tmp_path)})
    assert p.returncode == 0, p.stderr
    assert p.stdout.split() == ["claude"]


def test_enabled_providers_reads_uncommented_lines_dedup_sorted(
        tmp_path: Path) -> None:
    (tmp_path / "Asterism.yaml").write_text(textwrap.dedent("""\
        formalizer:
          provider: codex
          model: x
        strategist:
          # provider: antigravity
          provider: zen
        adversary:
          provider: claude
        judge:
          provider: codex
        """), encoding="utf-8")
    p = _run('ROOT="$FAKE_ROOT"\nenabled_providers',
            env_extra={"FAKE_ROOT": str(tmp_path)})
    assert p.returncode == 0, p.stderr
    assert p.stdout.split() == ["claude", "codex", "zen"]
    assert "antigravity" not in p.stdout


def test_enabled_providers_ignores_fully_commented_line(
        tmp_path: Path) -> None:
    (tmp_path / "Asterism.yaml").write_text(
        "# provider: antigravity\n", encoding="utf-8")
    p = _run('ROOT="$FAKE_ROOT"\nenabled_providers',
            env_extra={"FAKE_ROOT": str(tmp_path)})
    assert p.returncode == 0, p.stderr
    assert p.stdout.split() == ["claude"]


# --------------------------------------------------------------------
# provider_json_get: the JSON seam onto provider-info.py's output
# --------------------------------------------------------------------

def test_provider_json_get_reads_scalar_and_null_fields() -> None:
    doc = ('{"name":"zen","installed":true,"env_key":"OPENROUTER_API_KEY",'
          '"install_command":null}')
    p = _run(f"provider_json_get '{doc}' installed")
    assert p.stdout.strip() == "True"
    p = _run(f"provider_json_get '{doc}' env_key")
    assert p.stdout.strip() == "OPENROUTER_API_KEY"
    p = _run(f"provider_json_get '{doc}' install_command")
    assert p.stdout.strip() == ""


def test_provider_info_py_seam_is_real_for_every_enabled_provider() -> None:
    """End-to-end through the real provider-info.py (no network — plain
    declaration read, no --check), for the providers this repo's own
    Asterism.yaml actually seats. Catches a JSON-shape drift between
    capabilities.py and this script's field names."""
    p = _run(
        'for prov in claude codex zen; do\n'
        '  info="$("$PY" "$ROOT/installer/provider-info.py" "$prov")"\n'
        '  provider_json_get "$info" install_method\n'
        'done'
    )
    assert p.returncode == 0, p.stderr
    lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
    assert lines == ["by_command", "by_command", "not_needed"]


# --------------------------------------------------------------------
# install_provider_cli: the one deliberate name branch (npm targets)
# --------------------------------------------------------------------

def test_install_provider_cli_npm_targets_invoke_npm(tmp_path: Path) -> None:
    log = tmp_path / "npm.log"
    bindir = _with_fake_bin(
        tmp_path, "npm", f'printf "%s\\n" "$@" >> "{log.as_posix()}"\n')
    import os
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
    for prov, pkg in (("claude", "@anthropic-ai/claude-code"),
                      ("codex", "@openai/codex"),
                      ("zen", "@openai/codex")):
        if log.exists():
            log.unlink()
        p = _run(f'install_provider_cli {prov}', env_extra=env)
        assert p.returncode == 0, p.stderr
        assert log.read_text(encoding="utf-8").split() == [
            "install", "-g", pkg]


def test_install_provider_cli_unknown_provider_returns_failure() -> None:
    for prov in ("antigravity", "gemini", "openai", "no-such-backend"):
        p = _run(f'install_provider_cli {prov} && echo CALLED || echo NOT-HANDLED')
        assert p.stdout.strip() == "NOT-HANDLED", (prov, p.stdout, p.stderr)


# --------------------------------------------------------------------
# check_leantar_arch: loud-fail-on-mismatch, OK-on-match, skip-on-unknown
# --------------------------------------------------------------------

def _fake_elan_file(tmp_path: Path, *, leantar_path: str,
                    file_report: str) -> Path:
    bindir = _with_fake_bin(
        tmp_path, "elan",
        f'if [ "$1" = which ] && [ "$2" = leantar ]; then '
        f'echo "{leantar_path}"; else echo "unsupported" >&2; exit 1; fi\n')
    (bindir / "file").write_text(
        f'#!/usr/bin/env bash\necho "{file_report}"\n', encoding="utf-8")
    (bindir / "file").chmod(0o755)
    return bindir


def test_check_leantar_arch_matching_host_is_ok(tmp_path: Path) -> None:
    import os
    bindir = _fake_elan_file(
        tmp_path, leantar_path="/opt/lean/bin/leantar",
        file_report="ELF 64-bit LSB pie executable, ARM aarch64, "
                    "version 1 (SYSV)")
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
    p = _run('check_leantar_arch', env_extra=env)
    # uname -m on this box is real (x86_64 under MSYS) — force the host
    # side via a fake uname reporting aarch64 so this is a true match.
    bindir2 = _with_fake_bin(tmp_path, "uname", 'echo aarch64\n')
    env["PATH"] = f"{bindir2}{os.pathsep}{env['PATH']}"
    p = _run('check_leantar_arch', env_extra=env)
    assert p.returncode == 0, (p.stdout, p.stderr)
    assert "OK" in p.stdout
    assert "matches host arch aarch64" in p.stdout


def test_check_leantar_arch_mismatch_fails_loud_without_fix_flag(
        tmp_path: Path) -> None:
    import os
    bindir = _fake_elan_file(
        tmp_path, leantar_path="/opt/lean/bin/leantar",
        file_report="ELF 64-bit LSB pie executable, x86-64, "
                    "version 1 (SYSV)")
    uname_dir = _with_fake_bin(tmp_path, "uname", 'echo aarch64\n')
    env = {"PATH": f"{uname_dir}{os.pathsep}{bindir}{os.pathsep}"
                   f"{os.environ.get('PATH', '')}",
           "FIX_LEANTAR": "0"}
    p = _run('check_leantar_arch', env_extra=env)
    assert p.returncode == 1
    combined = p.stdout + p.stderr
    assert "FAIL" in combined
    assert "x86_64 ELF" in combined or "is x86_64" in combined
    assert "exec-format error" in combined
    assert "digama0/leangz" in combined
    assert "lean-toolchain" in combined  # states the pin is untouched


def test_check_leantar_arch_unresolved_leantar_skips_not_fails(
        tmp_path: Path) -> None:
    """elan cannot resolve leantar yet (toolchain not installed) — this
    must SKIP with an explanatory note, not fail the installer."""
    import os
    bindir = _with_fake_bin(
        tmp_path, "elan",
        'if [ "$1" = which ]; then exit 1; fi\n')
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
    p = _run('check_leantar_arch', env_extra=env)
    assert p.returncode == 0, (p.stdout, p.stderr)
    assert "not yet resolved" in p.stdout


def test_check_leantar_arch_fix_flag_drives_the_fetch(tmp_path: Path
                                                       ) -> None:
    """--fix-leantar end to end through check_leantar_arch: a mismatch
    is detected, the opt-in flag is seen (parsed from "$@" at source
    time, mirroring how `main "$@"` would see it), and the fetch runs —
    network and `file` both stubbed."""
    import os
    target = tmp_path / "leantar"
    target.write_bytes(b"old-x86-64-binary")
    archive = _make_fake_archive(tmp_path, "leantar",
                                 content=b"new-aarch64-binary")

    elan_dir = _fake_elan_file(
        tmp_path, leantar_path=target.as_posix(),
        file_report="ELF 64-bit LSB pie executable, x86-64, "
                    "version 1 (SYSV)")
    uname_dir = _with_fake_bin(tmp_path, "uname", 'echo aarch64\n')
    curl_dir = _with_fake_bin(
        tmp_path, "curl",
        f'out=""\n'
        f'while [ $# -gt 0 ]; do\n'
        f'  if [ "$1" = "-o" ]; then out="$2"; fi\n'
        f'  shift\n'
        f'done\n'
        f'cp "{archive.as_posix()}" "$out"\n')
    # `file` must report x86-64 for the ORIGINAL mismatch check, then
    # aarch64 for the post-replace recheck — keyed on the path so both
    # calls (before and after the swap) get the right answer.
    file_script = tmp_path / "fakebin" / "file"
    file_script.write_text(
        f'#!/usr/bin/env bash\n'
        f'if cmp -s "$1" "{archive.as_posix()}" 2>/dev/null; then :; fi\n'
        f'if [ "$(wc -c < "$1")" = "{len(b"new-aarch64-binary")}" ]; then\n'
        f'  echo "ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV)"\n'
        f'else\n'
        f'  echo "ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV)"\n'
        f'fi\n', encoding="utf-8")
    file_script.chmod(0o755)

    env = {"PATH": f"{uname_dir}{os.pathsep}{elan_dir}{os.pathsep}"
                   f"{curl_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
    p = _run('check_leantar_arch', env_extra=env, argv=["--fix-leantar"])
    assert p.returncode == 0, (p.stdout, p.stderr)
    assert "FAIL" in p.stdout  # the loud report still prints first
    assert "fetching the correct build now" in p.stdout
    assert "replaced" in p.stdout
    assert target.read_bytes() == b"new-aarch64-binary"


# --------------------------------------------------------------------
# fetch_and_replace_leantar: the opt-in mutation, network stubbed out
# --------------------------------------------------------------------

def _make_fake_archive(tmp_path: Path, binary_name: str,
                       content: bytes = b"fake-elf-bytes") -> Path:
    """Builds a .tar.gz containing one file named `binary_name`. Stages
    it under its OWN subdirectory rather than directly in `tmp_path` —
    `binary_name` is always "leantar", the same basename tests also use
    for the real target/leantar path in `tmp_path`, and staging in
    `tmp_path` directly silently clobbered that target file (both
    `Path.write_bytes` calls resolved to the identical path), corrupting
    the "before replace" content the mismatch tests depend on."""
    stage = tmp_path / "_archive_stage"
    stage.mkdir(exist_ok=True)
    src = stage / binary_name
    src.write_bytes(content)
    archive = tmp_path / "leantar.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(src, arcname=binary_name)
    return archive


def test_fetch_and_replace_leantar_success(tmp_path: Path) -> None:
    import os
    target = tmp_path / "leantar"
    target.write_bytes(b"old-wrong-arch-binary")
    archive = _make_fake_archive(tmp_path, "leantar")

    curl_dir = _with_fake_bin(
        tmp_path, "curl",
        f'out=""\n'
        f'while [ $# -gt 0 ]; do\n'
        f'  if [ "$1" = "-o" ]; then out="$2"; fi\n'
        f'  shift\n'
        f'done\n'
        f'cp "{archive.as_posix()}" "$out"\n')
    file_dir = _with_fake_bin(
        tmp_path, "file",
        'echo "ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV)"\n')
    env = {"PATH": f"{curl_dir}{os.pathsep}{file_dir}{os.pathsep}"
                   f"{os.environ.get('PATH', '')}"}
    p = _run(
        f'target="{target.as_posix()}"\n'
        f'fetch_and_replace_leantar "$target" aarch64',
        env_extra=env)
    assert p.returncode == 0, (p.stdout, p.stderr)
    assert "replaced" in p.stdout
    assert target.read_bytes() == b"fake-elf-bytes"
    backups = list(tmp_path.glob("leantar.bak-*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"old-wrong-arch-binary"


def test_fetch_and_replace_leantar_empty_archive_aborts(
        tmp_path: Path) -> None:
    import os
    target = tmp_path / "leantar"
    target.write_bytes(b"old")
    empty_archive = tmp_path / "empty.tar.gz"
    with tarfile.open(empty_archive, "w:gz"):
        pass  # no members at all

    curl_dir = _with_fake_bin(
        tmp_path, "curl",
        f'out=""\n'
        f'while [ $# -gt 0 ]; do\n'
        f'  if [ "$1" = "-o" ]; then out="$2"; fi\n'
        f'  shift\n'
        f'done\n'
        f'cp "{empty_archive.as_posix()}" "$out"\n')
    env = {"PATH": f"{curl_dir}{os.pathsep}{os.environ.get('PATH', '')}"}
    p = _run(
        f'target="{target.as_posix()}"\n'
        f'fetch_and_replace_leantar "$target" aarch64',
        env_extra=env)
    assert p.returncode == 1
    assert "did not contain a leantar binary" in (p.stdout + p.stderr)
    # the ORIGINAL binary must survive an aborted replace
    assert target.read_bytes() == b"old"


# --------------------------------------------------------------------
# system deps / step numbering sanity (no execution of steps needed)
# --------------------------------------------------------------------

def test_step_prints_out_of_eight() -> None:
    p = _run('step 3 "Widgets"')
    assert p.returncode == 0, p.stderr
    assert "[3/8]" in p.stdout


def test_fix_leantar_flag_parsing() -> None:
    p = _run('echo "$FIX_LEANTAR"')
    assert p.stdout.strip() == "0"
