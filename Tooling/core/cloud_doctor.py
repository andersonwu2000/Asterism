"""`asterism doctor --cloud`: Oracle Ampere A1 (Ubuntu 24.04 ARM64)
readiness checks, called from `cli.cmd_doctor`.

Scope is P0#1 / P1#6 of `docs/internal/dev/oracle_arm64_cloud_readiness.md`
— VISIBILITY only. Memory-cap ENFORCEMENT (P0#3), Linux process-tree
lifecycle (P0#2), the Linux attempt-path regex (P0#4) and systemd units
(P1#7) are separate, unstarted work; this module answers "is the box
ready", never "make the box ready".

Every check here is a pure function of injectable inputs (a root path,
a listener list, a `run`/`which` callable) PLUS a thin wrapper that
supplies the real OS state — the split exists so the pure half is
testable on Windows (where none of the real Linux paths exist) without
mocking half the standard library, and the wrapper half is what
`cmd_doctor` actually calls. Every wrapper degrades to a SKIP verdict
rather than raising: doctor's job is to report the machine's readiness,
not to crash while doing it, and the whole module must run cleanly on
the Windows dev box (`pytest` runs there) as well as on the target VM.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

#: (status, message) — the same tri-state `cmd_doctor` already prints
#: OK/FAIL/WARN lines in, plus SKIP for "not applicable on this OS" or
#: "could not be measured from here" (an unknown must not masquerade as
#: a pass, the same ruling `capabilities.py` makes for an undeclared
#: provider).
Verdict = "dict[str, str]"  # {"verdict": "OK"|"FAIL"|"WARN"|"SKIP", "detail": str}


def _v(verdict: str, detail: str) -> Verdict:
    return {"verdict": verdict, "detail": detail}


# --------------------------------------------------------- OS / arch

def os_arch() -> Verdict:
    """`platform.machine()` is the whole check the work order asks for
    here — no assumption about which arch is "right", just print it so
    a silent x86-64-on-ARM assumption (the leantar failure mode) cannot
    hide behind an installer that never looked."""
    return _v("OK", f"{platform.system()} {platform.release()} "
                     f"machine={platform.machine()}")


# --------------------------------------------------------- CPU/RAM/disk

def resources(workspace: Path) -> Verdict:
    """CPU count, total RAM, free disk on the workspace volume. All
    three come from stdlib/psutil reads that cannot fail under normal
    conditions; SKIP (not FAIL) if the platform refuses one — a resource
    probe erroring is not evidence the machine is unfit."""
    cpu = None
    ram_bytes = None
    try:
        import psutil
        cpu = psutil.cpu_count(logical=True)
        ram_bytes = psutil.virtual_memory().total
    except Exception as exc:  # noqa: BLE001 — best-effort resource probe
        return _v("SKIP", f"could not read CPU/RAM via psutil: {exc}")
    try:
        disk = shutil.disk_usage(workspace)
    except OSError as exc:
        return _v("SKIP", f"could not read disk usage for {workspace}: {exc}")
    ram_gb = ram_bytes / (1024 ** 3) if ram_bytes else None
    disk_free_gb = disk.free / (1024 ** 3)
    disk_total_gb = disk.total / (1024 ** 3)
    detail = (f"cpu={cpu} ram={ram_gb:.1f}GB "
              f"disk_free={disk_free_gb:.1f}GB/{disk_total_gb:.1f}GB "
              f"on {workspace}")
    return _v("OK", detail)


# --------------------------------------------------------- cgroup v2

def cgroup_v2_present(cgroup_root: Path) -> bool:
    """The presence check the work order names explicitly:
    `/sys/fs/cgroup/cgroup.controllers` readable."""
    try:
        return (cgroup_root / "cgroup.controllers").is_file()
    except OSError:
        return False


def own_cgroup_path(proc_self_cgroup_text: str) -> "str | None":
    """Parse `/proc/self/cgroup` (cgroup v2 unified hierarchy: exactly
    one line, `0::<path>`) into the path segment, or None if the text is
    not that shape (cgroup v1 multi-line, or unreadable upstream)."""
    for line in proc_self_cgroup_text.splitlines():
        parts = line.split(":", 2)
        if len(parts) == 3 and parts[0] == "0" and parts[1] == "":
            return parts[2]
    return None


def memory_cap_from_tree(cgroup_root: Path, own_path: "str | None",
                         read_text) -> Verdict:
    """Walk from this process's leaf cgroup UP to `cgroup_root`, and
    report whether ANY level on that walk sets a finite `memory.max`.

    Walking the whole chain rather than reading only the leaf matters:
    a systemd `MemoryHigh=`/`MemoryMax=` on a PARENT slice (e.g. a unit
    or user slice) constrains this process even when its own leaf
    cgroup declares no limit of its own (`memory.max` = `max`, the
    literal unlimited value) — a leaf-only read would report "no cap"
    under a working systemd-level cap, which is exactly the honest-
    visibility failure the work order is guarding against (P0#3 has not
    shipped ENFORCEMENT yet, so a false "no cap" here would be read as
    "nothing protects the host", which may already be false once
    systemd units land).

    `read_text` is injected (a `Path -> str | None` callable) so this is
    testable against a synthetic tree without touching the real
    filesystem — production passes a thin wrapper around
    `Path.read_text`.
    """
    if own_path is None:
        return _v("SKIP", "could not determine this process's cgroup "
                          "(unreadable or not a cgroup v2 unified path)")
    parts = [p for p in own_path.split("/") if p]
    for depth in range(len(parts), -1, -1):
        level_dir = cgroup_root.joinpath(*parts[:depth])
        val = read_text(level_dir / "memory.max")
        if val is None:
            continue
        val = val.strip()
        if val and val != "max":
            return _v("OK", f"memory cap enforced: yes "
                            f"({level_dir / 'memory.max'} = {val})")
    return _v("OK", "memory cap enforced: no (every level up to "
                    f"{cgroup_root} is unlimited or absent)")


def _real_read_text(path: Path) -> "str | None":
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def cgroup_memory_cap(cgroup_root: "Path | None" = None) -> Verdict:
    """Real-filesystem wrapper around `memory_cap_from_tree`. Reports
    "cap enforced: yes/no" on Linux with a readable cgroup v2 tree, and
    "not-linux" everywhere else — including a Linux host stuck on
    cgroup v1, since this module implements no v1 reading (P0#3 scope)."""
    if platform.system() != "Linux":
        return _v("SKIP", "cap enforced: not-linux")
    root = cgroup_root or Path("/sys/fs/cgroup")
    if not cgroup_v2_present(root):
        return _v("WARN", "cap enforced: no (no cgroup v2 unified "
                          f"hierarchy at {root} — cgroup.controllers "
                          "unreadable; a v1-only host cannot be capped "
                          "by this framework)")
    proc_cgroup = _real_read_text(Path("/proc/self/cgroup"))
    if proc_cgroup is None:
        return _v("SKIP", "cgroup v2 present but /proc/self/cgroup "
                          "unreadable — cannot locate this process's cgroup")
    own_path = own_cgroup_path(proc_cgroup)
    verdict = memory_cap_from_tree(root, own_path, _real_read_text)
    if verdict["verdict"] == "OK" and "enforced: no" in verdict["detail"]:
        # Honest visibility, not a failure: P0#3 (real enforcement) has
        # not shipped, so "no" is the expected answer everywhere until
        # then — WARN would fire on every doctor run before that lands.
        return verdict
    return verdict


# --------------------------------------------------------- leantar arch

def classify_host_arch(machine: str) -> str:
    """Normalize `platform.machine()` / `uname -m` spellings to the two
    families that matter here. Mirrors `installer/install.sh`'s own
    normalization — the two must agree, or a doctor OK could sit beside
    an installer FAIL for the identical machine."""
    low = machine.strip().lower()
    if low in ("aarch64", "arm64"):
        return "aarch64"
    if low in ("x86_64", "amd64", "x64"):
        return "x86_64"
    return "unknown"


def classify_elf_arch(file_output: str) -> str:
    """Classify a `file <binary>` textual report into the same two
    families. `file`'s wording for an ARM64 ELF is "ARM aarch64"; for
    x86-64 it is "x86-64" (with a hyphen, not underscore)."""
    low = file_output.lower()
    if "aarch64" in low or "arm64" in low:
        return "aarch64"
    if "x86-64" in low or "x86_64" in low:
        return "x86_64"
    return "unknown"


def leantar_status(*, which=None, run=None) -> Verdict:
    """Same check the installer runs before `lake build`, here read-only
    (no fetch-and-replace — that is the installer's `--fix-leantar`,
    an opt-in mutation doctor must never perform on its own).

    `which`/`run` are injected (default `shutil.which` / `subprocess.run`)
    so the whole decision tree is testable without a real elan install."""
    which = which or shutil.which
    run = run or subprocess.run
    elan = which("elan")
    if not elan:
        return _v("SKIP", "elan not on PATH")
    try:
        r = run([elan, "which", "leantar"],
               capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        return _v("SKIP", f"`elan which leantar` failed: {exc}")
    path = (r.stdout or "").strip()
    if r.returncode != 0 or not path:
        return _v("SKIP", "leantar not resolved by elan (toolchain not "
                          "installed yet — run the installer first)")
    file_exe = which("file")
    if not file_exe:
        return _v("SKIP", f"leantar at {path}, but no `file` on PATH to "
                          f"check its architecture")
    try:
        r2 = run([file_exe, path], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as exc:
        return _v("SKIP", f"`file {path}` failed: {exc}")
    observed = classify_elf_arch(r2.stdout or "")
    host = classify_host_arch(platform.machine())
    if observed == "unknown":
        return _v("SKIP", f"could not classify `file` output for {path}: "
                          f"{(r2.stdout or '').strip()!r}")
    if host == "unknown":
        return _v("SKIP", f"unrecognized host arch {platform.machine()!r}")
    if observed == host:
        return _v("OK", f"leantar ({path}) matches host arch {host}")
    return _v("FAIL", (
        f"leantar ({path}) is {observed} ELF but host is {host} — lake "
        f"cache/build will fail. Fix: bash installer/install.sh "
        f"--fix-leantar (fetches leantar-v0.1.19-{host}-unknown-linux-musl "
        f"from https://github.com/digama0/leangz/releases and replaces "
        f"the binary; never touches the Lean pin)"))


def lean_toolchain_presence(*, which=None) -> "dict[str, Verdict]":
    which = which or shutil.which
    out: "dict[str, Verdict]" = {}
    for exe in ("elan", "lean", "lake"):
        p = which(exe)
        out[exe] = _v("OK", p) if p else _v("WARN", f"{exe} not on PATH")
    return out


# --------------------------------------------------------- python/node

def python_version() -> Verdict:
    v = sys.version.split()[0]
    if sys.version_info >= (3, 12):
        return _v("OK", f"python {v}")
    return _v("FAIL", f"python {v} — 3.12+ required")


def node_version(*, which=None, run=None) -> Verdict:
    which = which or shutil.which
    run = run or subprocess.run
    node = which("node")
    if not node:
        return _v("WARN", "node not on PATH (needed for the web build "
                          "and any npm-installed provider CLI)")
    try:
        r = run([node, "--version"], capture_output=True, text=True,
               timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        return _v("WARN", f"node --version failed: {exc}")
    v = (r.stdout or r.stderr or "").strip() or "?"
    return _v("OK", f"node {v}")


# --------------------------------------------------------- providers

def enabled_providers(workspace: "Path | None" = None) -> "list[str]":
    """Every provider actually seated on a pipeline kind right now — the
    same live read `seat_banner()` uses, not a hard-coded claude-only
    list. `Asterism.yaml` is live-editable and a seat can move providers
    between runs, so this is re-derived per call rather than cached."""
    from . import dispatcher
    from ..llm import capabilities as caps
    seats = dispatcher._pipeline_seats()
    return sorted({caps.canonical(prov) for prov, _model in seats.values()})


def provider_presence(name: str, *, which=None) -> Verdict:
    """Is this provider's CLI on PATH? Presence only — no readiness
    round-trip (that costs a network call per provider and doctor
    --cloud should stay fast). Resolution order mirrors the two other
    places that already do this per-provider dance
    (`installer/provider-info.py::_measure`, `serve/app.py::_provider_rows`):
    claude/antigravity own a resolver, everyone else is `cap.exe_name`
    or the provider's own name."""
    which = which or shutil.which
    from ..llm import capabilities as caps
    cap = caps.capabilities_for(name)
    exe = None
    if name == "claude":
        from ..llm.claude_cli import resolve_claude_executable
        exe = resolve_claude_executable()
    elif name == "antigravity":
        from ..llm.antigravity_cli import resolve_agy_executable
        exe = resolve_agy_executable()
    elif cap.exe_name is not None:
        exe = which(cap.exe_name)
    elif cap.install_method == caps.INSTALL_NOT_NEEDED:
        return _v("OK", f"{name}: reached over HTTP, no CLI needed")
    else:
        exe = which(name)
    if exe:
        return _v("OK", f"{name}: {exe}")
    return _v("WARN", f"{name}: CLI not found on PATH "
                      f"(install_command={cap.install_command!r})")


# --------------------------------------------------------- ports

def classify_port(port: int, listeners: "list[tuple[str, int]]") -> Verdict:
    """Pure decision given an already-filtered list of `(ip, port)`
    LISTEN-state sockets system-wide: OK/free, OK/localhost-only, or
    FAIL if anything is bound on a non-loopback address — the exact
    posture P1#8 requires (8642/8765/8898 must never reach the public
    interface on a cloud box)."""
    hits = sorted({ip for ip, p in listeners if p == port})
    if not hits:
        return _v("OK", f"port {port}: free")
    non_local = sorted(ip for ip in hits if ip not in ("127.0.0.1", "::1"))
    if non_local:
        return _v("FAIL", f"port {port}: bound on {', '.join(non_local)} "
                          f"— not localhost-only")
    return _v("OK", f"port {port}: bound on localhost only "
                    f"({', '.join(hits)})")


def port_status(port: int, *,
                listeners: "list[tuple[str, int]] | None" = None) -> Verdict:
    """Real-world wrapper: enumerate system LISTEN sockets via psutil and
    hand them to `classify_port`. `listeners` can be injected directly
    (bypassing psutil) for tests. SKIP, not FAIL, if enumeration itself
    is refused (e.g. no permission) — that says nothing about the port."""
    if listeners is None:
        try:
            import psutil
            conns = psutil.net_connections(kind="inet")
            listeners = [
                (c.laddr.ip, c.laddr.port) for c in conns
                if getattr(c, "status", None) == psutil.CONN_LISTEN
                and c.laddr]
        except Exception as exc:  # noqa: BLE001 — psutil can need admin
            return _v("SKIP", f"could not enumerate listening sockets "
                              f"(port {port}): {exc}")
    return classify_port(port, listeners)


#: The three ports P1#8's security-default check covers.
CLOUD_PORTS = {"gateway": 8765, "shim": 8898, "web": 8642}
