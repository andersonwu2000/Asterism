"""`Tooling/core/cloud_doctor.py` — the pure decision functions behind
`asterism doctor --cloud` (Oracle ARM64 readiness,
docs/internal/dev/oracle_arm64_cloud_readiness.md P0#1/P1#6).

Every function under test here is a pure function of injectable inputs
(a synthetic filesystem tree via a `read_text` stub, a fake `which`/
`run`, an explicit listener list) — none of them touch a real `/proc`
or `/sys/fs/cgroup` (which do not exist on this Windows dev box, where
this suite runs), a real elan install, or a real socket table. The
`cmd_doctor_cloud` end-to-end wrapper is covered separately in
`test_cli_doctor.py` (it must not raise on Windows)."""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from Tooling.core import cloud_doctor as cd


# --------------------------------------------------------------------
# os / resources
# --------------------------------------------------------------------

def test_os_arch_is_always_ok_and_names_platform_machine() -> None:
    v = cd.os_arch()
    assert v["verdict"] == "OK"
    assert platform.machine() in v["detail"]


def test_resources_reports_cpu_ram_disk(tmp_path: Path) -> None:
    v = cd.resources(tmp_path)
    assert v["verdict"] == "OK"
    assert "cpu=" in v["detail"]
    assert "ram=" in v["detail"]
    assert "disk_free=" in v["detail"]


def test_resources_skips_rather_than_raises_on_bad_workspace(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_path):
        raise OSError("no such volume")
    monkeypatch.setattr(cd.shutil, "disk_usage", _boom)
    v = cd.resources(tmp_path)
    assert v["verdict"] == "SKIP"


def test_resources_skips_when_psutil_unavailable(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    real_import = builtins.__import__

    def _fake_import(name, *a, **kw):
        if name == "psutil":
            raise ImportError("no psutil")
        return real_import(name, *a, **kw)
    monkeypatch.setattr(builtins, "__import__", _fake_import)
    v = cd.resources(tmp_path)
    assert v["verdict"] == "SKIP"


# --------------------------------------------------------------------
# cgroup v2 presence / own-cgroup parsing
# --------------------------------------------------------------------

def test_cgroup_v2_present_true_when_controllers_file_exists(
        tmp_path: Path) -> None:
    (tmp_path / "cgroup.controllers").write_text("cpu io memory\n")
    assert cd.cgroup_v2_present(tmp_path) is True


def test_cgroup_v2_present_false_when_missing(tmp_path: Path) -> None:
    assert cd.cgroup_v2_present(tmp_path) is False


@pytest.mark.parametrize("text,want", [
    ("0::/user.slice/user-1000.slice/session-1.scope",
     "/user.slice/user-1000.slice/session-1.scope"),
    ("0::/\n", "/"),
    # cgroup v1 multi-line shape — not the unified path this parser
    # understands, so None (SKIP upstream), not a wrong guess.
    ("12:pids:/user.slice\n1:name=systemd:/user.slice\n0::/\n", "/"),
    ("11:memory:/docker/abc123\n10:cpu,cpuacct:/docker/abc123\n", None),
    ("", None),
])
def test_own_cgroup_path(text: str, want: "str | None") -> None:
    assert cd.own_cgroup_path(text) == want


# --------------------------------------------------------------------
# memory_cap_from_tree — the walk-up-the-chain logic
# --------------------------------------------------------------------

def _stub_reader(files: "dict[str, str]"):
    def _read(path: Path) -> "str | None":
        return files.get(str(path).replace("\\", "/"))
    return _read


def test_memory_cap_none_own_path_is_skip(tmp_path: Path) -> None:
    v = cd.memory_cap_from_tree(tmp_path, None, _stub_reader({}))
    assert v["verdict"] == "SKIP"


def test_memory_cap_all_levels_unlimited_is_ok_no(tmp_path: Path) -> None:
    root = tmp_path
    own = "/a.slice/b.slice"
    files = {
        f"{(root / 'a.slice' / 'b.slice' / 'memory.max').as_posix()}": "max",
        f"{(root / 'a.slice' / 'memory.max').as_posix()}": "max",
        f"{(root / 'memory.max').as_posix()}": "max",
    }
    v = cd.memory_cap_from_tree(root, own, _stub_reader(files))
    assert v["verdict"] == "OK"
    assert "enforced: no" in v["detail"]


def test_memory_cap_leaf_finite_is_enforced_yes(tmp_path: Path) -> None:
    root = tmp_path
    own = "/a.slice/b.slice"
    leaf = (root / "a.slice" / "b.slice" / "memory.max").as_posix()
    v = cd.memory_cap_from_tree(root, own, _stub_reader({leaf: "8388608000\n"}))
    assert v["verdict"] == "OK"
    assert "enforced: yes" in v["detail"]
    assert "8388608000" in v["detail"]


def test_memory_cap_parent_slice_finite_is_still_enforced_yes(
        tmp_path: Path) -> None:
    """The whole reason to walk the chain: the LEAF is unlimited but a
    PARENT systemd slice caps it — must still read "yes", not "no"."""
    root = tmp_path
    own = "/a.slice/b.slice"
    leaf = (root / "a.slice" / "b.slice" / "memory.max").as_posix()
    parent = (root / "a.slice" / "memory.max").as_posix()
    v = cd.memory_cap_from_tree(
        root, own, _stub_reader({leaf: "max", parent: "4000000000"}))
    assert v["verdict"] == "OK"
    assert "enforced: yes" in v["detail"]
    assert "4000000000" in v["detail"]


def test_memory_cap_missing_files_treated_as_absent_not_error(
        tmp_path: Path) -> None:
    v = cd.memory_cap_from_tree(tmp_path, "/nope/at/all", _stub_reader({}))
    assert v["verdict"] == "OK"
    assert "enforced: no" in v["detail"]


def test_cgroup_memory_cap_wrapper_reports_not_linux_on_this_box() -> None:
    """This suite runs on Windows — the real wrapper must SKIP cleanly,
    never raise, regardless of what /proc or /sys look like here."""
    v = cd.cgroup_memory_cap()
    assert v["verdict"] == "SKIP"
    assert "not-linux" in v["detail"]


# --------------------------------------------------------------------
# arch classification (kept in lockstep with installer/install.sh's
# classify_host_arch / classify_elf_arch — see test_installer_install_sh.py)
# --------------------------------------------------------------------

@pytest.mark.parametrize("machine,want", [
    ("aarch64", "aarch64"), ("arm64", "aarch64"), ("ARM64", "aarch64"),
    ("x86_64", "x86_64"), ("amd64", "x86_64"), ("x64", "x86_64"),
    ("riscv64", "unknown"), ("", "unknown"),
])
def test_classify_host_arch(machine: str, want: str) -> None:
    assert cd.classify_host_arch(machine) == want


@pytest.mark.parametrize("file_output,want", [
    ("ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV)",
     "aarch64"),
    ("ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV)", "x86_64"),
    ("PE32+ executable (console) x86-64", "x86_64"),
    ("ASCII text", "unknown"),
])
def test_classify_elf_arch(file_output: str, want: str) -> None:
    assert cd.classify_elf_arch(file_output) == want


# --------------------------------------------------------------------
# leantar_status — injected which/run, no real elan/file needed
# --------------------------------------------------------------------

class _Proc(SimpleNamespace):
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


def test_leantar_status_skip_when_elan_absent() -> None:
    v = cd.leantar_status(which=lambda name: None)
    assert v["verdict"] == "SKIP"
    assert "elan not on PATH" in v["detail"]


def test_leantar_status_skip_when_leantar_unresolved() -> None:
    def run(argv, **kw):
        return _Proc(returncode=1, stdout="")
    v = cd.leantar_status(which=lambda name: f"/bin/{name}", run=run)
    assert v["verdict"] == "SKIP"
    assert "not resolved" in v["detail"]


def test_leantar_status_skip_when_file_tool_absent() -> None:
    def which(name):
        return "/bin/elan" if name == "elan" else None
    def run(argv, **kw):
        return _Proc(returncode=0, stdout="/opt/lean/bin/leantar\n")
    v = cd.leantar_status(which=which, run=run)
    assert v["verdict"] == "SKIP"
    assert "no `file` on PATH" in v["detail"]


def test_leantar_status_ok_on_arch_match(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cd.platform, "machine", lambda: "aarch64")
    def which(name):
        return f"/bin/{name}"
    def run(argv, **kw):
        if argv[1:3] == ["which", "leantar"]:
            return _Proc(returncode=0, stdout="/opt/lean/bin/leantar\n")
        return _Proc(returncode=0, stdout="ELF 64-bit LSB pie executable, "
                                          "ARM aarch64, version 1 (SYSV)")
    v = cd.leantar_status(which=which, run=run)
    assert v["verdict"] == "OK"
    assert "matches host arch aarch64" in v["detail"]


def test_leantar_status_fail_on_arch_mismatch_names_the_fix(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cd.platform, "machine", lambda: "aarch64")
    def which(name):
        return f"/bin/{name}"
    def run(argv, **kw):
        if argv[1:3] == ["which", "leantar"]:
            return _Proc(returncode=0, stdout="/opt/lean/bin/leantar\n")
        return _Proc(returncode=0, stdout="ELF 64-bit LSB pie executable, "
                                          "x86-64, version 1 (SYSV)")
    v = cd.leantar_status(which=which, run=run)
    assert v["verdict"] == "FAIL"
    assert "digama0/leangz" in v["detail"]
    assert "--fix-leantar" in v["detail"]
    assert "x86_64" in v["detail"] and "aarch64" in v["detail"]


def test_leantar_status_skip_on_unclassifiable_file_output(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cd.platform, "machine", lambda: "aarch64")
    def which(name):
        return f"/bin/{name}"
    def run(argv, **kw):
        if argv[1:3] == ["which", "leantar"]:
            return _Proc(returncode=0, stdout="/opt/lean/bin/leantar\n")
        return _Proc(returncode=0, stdout="data")
    v = cd.leantar_status(which=which, run=run)
    assert v["verdict"] == "SKIP"


def test_leantar_status_skip_on_subprocess_error() -> None:
    def which(name):
        return f"/bin/{name}"
    def run(argv, **kw):
        raise OSError("boom")
    v = cd.leantar_status(which=which, run=run)
    assert v["verdict"] == "SKIP"


def test_lean_toolchain_presence_reports_each_tool() -> None:
    present = {"elan", "lake"}
    out = cd.lean_toolchain_presence(
        which=lambda name: f"/bin/{name}" if name in present else None)
    assert out["elan"]["verdict"] == "OK"
    assert out["lake"]["verdict"] == "OK"
    assert out["lean"]["verdict"] == "WARN"


# --------------------------------------------------------------------
# python / node
# --------------------------------------------------------------------

def test_python_version_ok_under_this_suite() -> None:
    # The suite is required to run under 3.12+ (D:\...\Python312\python.exe)
    v = cd.python_version()
    assert v["verdict"] == "OK"


def test_node_version_warn_when_absent() -> None:
    v = cd.node_version(which=lambda name: None)
    assert v["verdict"] == "WARN"


def test_node_version_ok_when_present() -> None:
    def run(argv, **kw):
        return _Proc(returncode=0, stdout="v22.4.0\n")
    v = cd.node_version(which=lambda name: "/bin/node", run=run)
    assert v["verdict"] == "OK"
    assert "v22.4.0" in v["detail"]


def test_node_version_warn_not_raise_on_subprocess_error() -> None:
    def run(argv, **kw):
        raise subprocess.TimeoutExpired(cmd="node", timeout=10)
    v = cd.node_version(which=lambda name: "/bin/node", run=run)
    assert v["verdict"] == "WARN"


# --------------------------------------------------------------------
# providers
# --------------------------------------------------------------------

def test_enabled_providers_reads_live_pipeline_seats(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from Tooling.core import dispatcher
    monkeypatch.setattr(dispatcher, "_pipeline_seats", lambda: {
        "formalizer": ("codex", "x"),
        "strategist": ("zen", None),
        "adversary": ("claude", None),
        "presearch": ("claude", None),
        "librarian": ("agy", None),  # alias -> antigravity
    })
    assert cd.enabled_providers() == [
        "antigravity", "claude", "codex", "zen"]


def test_provider_presence_claude_uses_its_own_resolver(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from Tooling.llm import claude_cli
    monkeypatch.setattr(claude_cli, "resolve_claude_executable",
                        lambda: "/opt/claude/bin/claude")
    v = cd.provider_presence("claude")
    assert v["verdict"] == "OK"
    assert "/opt/claude/bin/claude" in v["detail"]


def test_provider_presence_claude_warn_when_unresolved(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from Tooling.llm import claude_cli
    monkeypatch.setattr(claude_cli, "resolve_claude_executable",
                        lambda: None)
    v = cd.provider_presence("claude")
    assert v["verdict"] == "WARN"


def test_provider_presence_antigravity_uses_its_own_resolver(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from Tooling.llm import antigravity_cli
    monkeypatch.setattr(antigravity_cli, "resolve_agy_executable",
                        lambda: "/opt/agy/bin/agy")
    v = cd.provider_presence("antigravity")
    assert v["verdict"] == "OK"


def test_provider_presence_zen_resolves_via_exe_name_codex(
        ) -> None:
    """zen has no CLI of its own — `capabilities.py` declares
    exe_name='codex', so presence must check for `codex` on PATH."""
    seen = []
    def which(name):
        seen.append(name)
        return "/bin/codex" if name == "codex" else None
    v = cd.provider_presence("zen", which=which)
    assert v["verdict"] == "OK"
    assert seen == ["codex"]


def test_provider_presence_codex_resolves_via_its_own_name() -> None:
    v = cd.provider_presence(
        "codex", which=lambda name: "/bin/codex" if name == "codex" else None)
    assert v["verdict"] == "OK"


def test_provider_presence_openai_needs_no_cli() -> None:
    v = cd.provider_presence("openai", which=lambda name: None)
    assert v["verdict"] == "OK"
    assert "no CLI needed" in v["detail"]


def test_provider_presence_missing_warns_and_names_install_command() -> None:
    v = cd.provider_presence("codex", which=lambda name: None)
    assert v["verdict"] == "WARN"
    assert "npm install -g @openai/codex" in v["detail"]


# --------------------------------------------------------------------
# ports
# --------------------------------------------------------------------

def test_classify_port_free() -> None:
    v = cd.classify_port(8765, [])
    assert v["verdict"] == "OK"
    assert "free" in v["detail"]


def test_classify_port_localhost_only_is_ok() -> None:
    v = cd.classify_port(8765, [("127.0.0.1", 8765), ("::1", 8765),
                                ("127.0.0.1", 9999)])
    assert v["verdict"] == "OK"
    assert "localhost only" in v["detail"]


def test_classify_port_public_bind_is_fail() -> None:
    v = cd.classify_port(8642, [("0.0.0.0", 8642)])
    assert v["verdict"] == "FAIL"
    assert "0.0.0.0" in v["detail"]
    assert "not localhost-only" in v["detail"]


def test_classify_port_mixed_binds_fail_names_the_non_local_one() -> None:
    v = cd.classify_port(8898, [("127.0.0.1", 8898), ("10.0.0.5", 8898)])
    assert v["verdict"] == "FAIL"
    assert "10.0.0.5" in v["detail"]


def test_port_status_uses_injected_listeners_bypassing_psutil() -> None:
    v = cd.port_status(8765, listeners=[("0.0.0.0", 8765)])
    assert v["verdict"] == "FAIL"


def test_port_status_skips_when_enumeration_itself_fails(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins
    real_import = builtins.__import__

    def _fake_import(name, *a, **kw):
        if name == "psutil":
            raise ImportError("blocked")
        return real_import(name, *a, **kw)
    monkeypatch.setattr(builtins, "__import__", _fake_import)
    v = cd.port_status(8765)
    assert v["verdict"] == "SKIP"


def test_cloud_ports_constant_has_the_three_documented_ports() -> None:
    assert cd.CLOUD_PORTS == {"gateway": 8765, "shim": 8898, "web": 8642}
