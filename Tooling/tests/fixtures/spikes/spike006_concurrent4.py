"""
spike-006: lake env lean 4-concurrent stress test
Extends spike-001 (3 concurrent) to 4 concurrent + different t_wall configs.
Compare with spike-001 warm-cache results.

Runs from D:/Hadamard cwd.
"""

import os
import subprocess
import threading
import time
from pathlib import Path

HADAMARD = Path("D:/Hadamard")
FIXTURES = Path(__file__).parent

# Lean files with import Mathlib (warm cache scenario)
MATHLIB_FILES = [
    FIXTURES / "spike001_mathlib_a.lean",
    FIXTURES / "spike001_mathlib_b.lean",
    FIXTURES / "spike001_mathlib_c.lean",
    FIXTURES / "spike001_mathlib_d.lean",
]

# Use spike001 files for non-Mathlib test
SIMPLE_FILES = [
    FIXTURES / "spike001_a.lean",
    FIXTURES / "spike001_b.lean",
    FIXTURES / "spike001_c.lean",
    FIXTURES / "spike001_a.lean",  # 4th worker reuses file
]


def run_one(lean_file: Path, cwd: Path, results: dict, idx: int):
    t0 = time.monotonic()
    proc = subprocess.run(
        ["lake", "env", "lean", str(lean_file)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.monotonic() - t0
    results[idx] = {
        "rc": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "elapsed": elapsed,
    }


def run_part(label: str, files: list, cwd: Path, sequential_first: bool = True):
    print(f"\n=== {label} ===")

    if sequential_first:
        # Sequential baseline (for comparison)
        print("Running sequential baseline (4 files in series)...")
        seq_results = {}
        t0 = time.monotonic()
        for i, f in enumerate(files):
            run_one(f, cwd, seq_results, i)
            r = seq_results[i]
            print(f"  [{i}] rc={r['rc']}, elapsed={r['elapsed']:.2f}s")
        seq_total = time.monotonic() - t0
        print(f"  Sequential total: {seq_total:.2f}s")
    else:
        seq_total = None

    # Concurrent (4 threads)
    print("Running 4-concurrent...")
    conc_results = {}
    threads = [
        threading.Thread(target=run_one, args=(f, cwd, conc_results, i))
        for i, f in enumerate(files)
    ]
    t0 = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    conc_total = time.monotonic() - t0

    all_ok = all(conc_results[i]["rc"] == 0 for i in range(len(files)))
    any_lock_error = any(
        "lock" in conc_results[i]["stderr"].lower() or "error" in conc_results[i]["stderr"].lower()
        for i in range(len(files))
    )
    print(f"  All rc=0: {all_ok}")
    print(f"  Any stderr error: {any_lock_error}")
    for i in range(len(files)):
        r = conc_results[i]
        print(f"  [{i}] rc={r['rc']}, elapsed={r['elapsed']:.2f}s, stderr={repr(r['stderr'][:80])}")
    print(f"  4-concurrent wall: {conc_total:.2f}s")

    if seq_total:
        speedup = seq_total / conc_total
        print(f"  Speedup vs sequential: {speedup:.2f}x")

    return {"seq_total": seq_total, "conc_total": conc_total, "all_ok": all_ok}


def main():
    print("spike-006: lake env lean 4-concurrent stress test")
    print(f"CWD: {HADAMARD}")
    print(f"Lake version: {subprocess.run(['lake', '--version'], cwd=str(HADAMARD), capture_output=True, text=True).stdout.strip()}")

    # Part 1: No Mathlib, 4 concurrent
    r1 = run_part(
        "Part 1 — No Mathlib, 4 concurrent",
        SIMPLE_FILES,
        HADAMARD,
        sequential_first=True,
    )

    # Part 2: Mathlib, 4 concurrent (warm cache)
    # First prime the cache with one sequential run
    print("\n=== Pre-warming Mathlib cache (1 file) ===")
    warm = subprocess.run(
        ["lake", "env", "lean", str(MATHLIB_FILES[0])],
        cwd=str(HADAMARD),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print(f"  Cache warm-up: rc={warm.returncode}, {len(warm.stdout)} bytes stdout")

    r2 = run_part(
        "Part 2 — Mathlib warm cache, 4 concurrent",
        MATHLIB_FILES,
        HADAMARD,
        sequential_first=False,  # skip sequential to save time
    )

    print("\n=== SUMMARY ===")
    print(f"Part 1 (no Mathlib): conc={r1['conc_total']:.2f}s, all_ok={r1['all_ok']}")
    print(f"Part 2 (Mathlib warm): conc={r2['conc_total']:.2f}s, all_ok={r2['all_ok']}")
    print()
    print("Compare with spike-001:")
    print("  spike-001 Part 1 (3-conc no Mathlib): 2.54s wall, sequential 7.29s, 2.87x speedup")
    print("  spike-001 Part 2 (3-conc Mathlib warm): 21.86s wall")


if __name__ == "__main__":
    main()
