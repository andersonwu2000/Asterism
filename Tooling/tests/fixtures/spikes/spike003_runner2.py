"""
spike-003 part 2: additional cases + timeout simulation.
"""
import subprocess
import sys
import io
import os
import signal
import threading

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HADAMARD_DIR = "D:\\Hadamard"
SPIKE_DIR = os.path.dirname(os.path.abspath(__file__))

def run(label, path, timeout_sec=60):
    try:
        r = subprocess.run(
            ["lake", "env", "lean", path],
            cwd=HADAMARD_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_sec,
        )
        stdout = r.stdout.decode("utf-8", errors="replace")
        stderr = r.stderr.decode("utf-8", errors="replace")
        print(f"\n{'='*60}")
        print(f"CASE: {label}")
        print(f"EXIT CODE: {r.returncode}")
        print(f"STDOUT: {repr(stdout[:500])}")
        print(f"STDERR: {repr(stderr[:200])}")
    except subprocess.TimeoutExpired as e:
        print(f"\n{'='*60}")
        print(f"CASE: {label}")
        print(f"EXIT CODE: TIMEOUT (after {timeout_sec}s)")
        stdout = (e.stdout or b"").decode("utf-8", errors="replace")
        stderr = (e.stderr or b"").decode("utf-8", errors="replace")
        print(f"PARTIAL STDOUT: {repr(stdout[:200])}")
        print(f"PARTIAL STDERR: {repr(stderr[:200])}")

cases = [
    ("type mismatch (def bad_type)", f"{SPIKE_DIR}\\spike003_more.lean"),
    ("unknown tactic", f"{SPIKE_DIR}\\spike003_unknown_tactic.lean"),
]

for label, path in cases:
    run(label, path)

# Test sorry detection regex
print("\n\n=== SORRY DETECTION RULE ===")
import re

sorry_pattern = re.compile(r"warning: declaration uses `sorry`")
error_pattern = re.compile(r":\s*error:")

test_cases = [
    ("pass (no warning)", ""),
    ("sorry warning", "D:\\foo.lean:3:8: warning: declaration uses `sorry`\n"),
    ("type error", "D:\\foo.lean:3:5: error: unsolved goals\n⊢ 1 = 2\n"),
    ("both sorry + error (shouldn't happen)", "D:\\foo.lean:3:8: warning: declaration uses `sorry`\nD:\\foo.lean:4:1: error: unknown\n"),
]

for label, output in test_cases:
    is_sorry = bool(sorry_pattern.search(output))
    is_error = bool(error_pattern.search(output))
    print(f"  [{label}] sorry={is_sorry} error={is_error}")
