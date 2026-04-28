"""spike-014: cancellation propagation 對 lake 子程序

測 `taskkill /F /T /PID <lake_pid>` 對 lake env lean 子程序樹的清理行為:
  - lake 程序本身死否
  - lake 的子孫程序 (lean.exe) 是否殘留
  - file handle leak (.olean 是否能立即重寫)

執行 (需 D:/Hadamard 已 warm cache):
    cd /d/Asterism && python Tooling/tests/fixtures/spikes/spike_014_lake_kill.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


HADAMARD_DIR = Path("D:/Hadamard")
TEST_LEAN_REL = "spike_014_test.lean"
TEST_LEAN_BODY = """\
import Hadamard
example : 1 + 1 = 2 := by decide
"""


def _count_lean_lake_processes() -> tuple[int, int]:
    """Returns (lean.exe count, lake.exe count) via tasklist."""
    out = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        capture_output=True, text=True,
    ).stdout
    lean_count = sum(1 for ln in out.splitlines() if '"lean.exe"' in ln)
    lake_count = sum(1 for ln in out.splitlines() if '"lake.exe"' in ln)
    return lean_count, lake_count


def _list_children(parent_pid: int) -> list[int]:
    """Walk descendants via wmic ParentProcessId."""
    out = subprocess.run(
        ["wmic", "process", "get", "ProcessId,ParentProcessId", "/FORMAT:CSV"],
        capture_output=True, text=True,
    ).stdout
    pairs: list[tuple[int, int]] = []
    for ln in out.splitlines()[1:]:
        parts = ln.strip().split(",")
        if len(parts) >= 3:
            try:
                ppid = int(parts[1].strip())
                pid = int(parts[2].strip())
                pairs.append((ppid, pid))
            except ValueError:
                continue

    # BFS descendants
    found: set[int] = set()
    frontier = [parent_pid]
    while frontier:
        nxt: list[int] = []
        for p in frontier:
            for ppid, pid in pairs:
                if ppid == p and pid not in found:
                    found.add(pid)
                    nxt.append(pid)
        frontier = nxt
    return sorted(found)


def main() -> int:
    if sys.platform != "win32":
        print("spike-014 designed for Windows only (taskkill /T)", file=sys.stderr)
        return 1

    # 0. Setup: write a test .lean that imports Hadamard
    test_lean = HADAMARD_DIR / TEST_LEAN_REL
    test_lean.write_text(TEST_LEAN_BODY, encoding="utf-8")

    try:
        # 1. Baseline: count lean/lake before
        b_lean, b_lake = _count_lean_lake_processes()
        print(f"baseline: lean.exe={b_lean} lake.exe={b_lake}")

        # 2. Spawn lake env lean
        t0 = time.monotonic()
        proc = subprocess.Popen(
            ["lake", "env", "lean", "--json", TEST_LEAN_REL],
            cwd=str(HADAMARD_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        print(f"spawned: pid={proc.pid}")

        # 3. Wait for child spawn (lake → lean handoff). Configurable via env.
        wait_s = float(os.environ.get("SPIKE_014_WAIT", "2.0"))
        time.sleep(wait_s)
        children_before = _list_children(proc.pid)
        m_lean, m_lake = _count_lean_lake_processes()
        print(f"mid-run: lean.exe={m_lean} lake.exe={m_lake}")
        print(f"mid-run children of lake({proc.pid}): {children_before}")

        # 4. Kill tree
        t_kill_start = time.monotonic()
        kill_rc = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True, text=True,
        )
        t_kill_done = time.monotonic()
        print(f"taskkill rc={kill_rc.returncode} took={t_kill_done-t_kill_start:.3f}s")
        print(f"  stdout: {kill_rc.stdout.strip()}")
        if kill_rc.stderr.strip():
            print(f"  stderr: {kill_rc.stderr.strip()}")

        # 5. wait + check survivors
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("ERROR: parent didn't exit within 5s after taskkill")
            return 2

        # Settle: give Windows a moment to reap
        time.sleep(0.5)
        a_lean, a_lake = _count_lean_lake_processes()
        children_after = _list_children(proc.pid)
        print(f"post-kill: lean.exe={a_lean} lake.exe={a_lake}")
        print(f"post-kill children of lake({proc.pid}): {children_after}")
        print(f"parent exit code: {proc.returncode}")
        print(f"total elapsed: {time.monotonic()-t0:.3f}s")

        # 6. File handle leak test: try removing the test .lean and overwriting cache
        try:
            test_lean.unlink()
            print("file unlink OK (no lock leak on test .lean)")
        except OSError as e:
            print(f"FILE LOCK LEAK on test .lean: {e}")

        # 7. Net process delta
        delta_lean = a_lean - b_lean
        delta_lake = a_lake - b_lake
        print(f"net delta: lean.exe={delta_lean:+d} lake.exe={delta_lake:+d}")
        if delta_lean > 0 or delta_lake > 0:
            print("WARN: leaked processes")
        else:
            print("OK: no leaked processes")

        return 0
    finally:
        if test_lean.exists():
            try:
                test_lean.unlink()
            except OSError:
                pass  # step 6 already reported leak; this is best-effort cleanup


if __name__ == "__main__":
    sys.exit(main())
