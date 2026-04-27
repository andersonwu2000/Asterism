"""
spike-003: Capture exact stdout/stderr/exitcode for each error scenario.
"""
import subprocess
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HADAMARD_DIR = "D:\\Hadamard"
SPIKE_DIR = os.path.dirname(os.path.abspath(__file__))

def run(label, path):
    r = subprocess.run(
        ["lake", "env", "lean", path],
        cwd=HADAMARD_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    stdout = r.stdout.decode("utf-8", errors="replace")
    stderr = r.stderr.decode("utf-8", errors="replace")
    print(f"\n{'='*60}")
    print(f"CASE: {label}")
    print(f"FILE: {os.path.basename(path)}")
    print(f"EXIT CODE: {r.returncode}")
    print(f"STDOUT ({len(stdout)} bytes):")
    print(repr(stdout))
    print(f"STDERR ({len(stderr)} bytes):")
    print(repr(stderr))

cases = [
    ("type_error (rfl on 1=2)", f"{SPIKE_DIR}\\spike003_type_error.lean"),
    ("sorry (warning only)", f"{SPIKE_DIR}\\spike003_sorry.lean"),
    ("sorry (multiple)", f"{SPIKE_DIR}\\spike003_sorry_multiple.lean"),
    ("unsolved goals", f"{SPIKE_DIR}\\spike003_unsolved.lean"),
]

for label, path in cases:
    try:
        run(label, path)
    except Exception as e:
        print(f"ERROR running {path}: {e}")
