"""
spike-001 part 2: Test concurrent lake env lean with import Mathlib.
"""
import subprocess
import threading
import time
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

HADAMARD_DIR = "D:\\Hadamard"
SPIKE_DIR = os.path.dirname(os.path.abspath(__file__))

files = [
    f"{SPIKE_DIR}\\spike001_mathlib_a.lean",
    f"{SPIKE_DIR}\\spike001_mathlib_b.lean",
    f"{SPIKE_DIR}\\spike001_mathlib_c.lean",
]

results = {}
errors = {}

def run_lean(path):
    start = time.time()
    try:
        r = subprocess.run(
            ["lake", "env", "lean", path],
            cwd=HADAMARD_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
        )
        elapsed = time.time() - start
        results[path] = {
            "returncode": r.returncode,
            "stdout": r.stdout.decode("utf-8", errors="replace"),
            "stderr": r.stderr.decode("utf-8", errors="replace"),
            "elapsed": elapsed,
        }
    except Exception as e:
        errors[path] = str(e)

print("=== spike-001 part 2: concurrent lake env lean WITH import Mathlib ===")
print(f"Running {len(files)} concurrent subprocesses...")

threads = [threading.Thread(target=run_lean, args=(f,)) for f in files]
t_start = time.time()
for t in threads:
    t.start()
for t in threads:
    t.join()
total = time.time() - t_start

print(f"Concurrent total wall-clock: {total:.2f}s")
print()

ok = True
for path, res in results.items():
    name = os.path.basename(path)
    rc = res["returncode"]
    elapsed = res["elapsed"]
    print(f"[{name}] rc={rc} elapsed={elapsed:.2f}s")
    if res["stderr"]:
        print(f"  stderr[:300]: {res['stderr'][:300]}")
    if res["stdout"]:
        print(f"  stdout[:300]: {res['stdout'][:300]}")
    if rc != 0:
        ok = False

for path, err in errors.items():
    print(f"[ERROR] {path}: {err}")
    ok = False

print()
print("RESULT:", "PASS - no conflicts with import Mathlib" if ok else "FAIL - errors occurred")

# Sequential for comparison
print()
print("=== Sequential run for comparison ===")
times_seq = []
for path in files:
    start = time.time()
    r = subprocess.run(
        ["lake", "env", "lean", path],
        cwd=HADAMARD_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=300,
    )
    elapsed = time.time() - start
    times_seq.append(elapsed)
    name = os.path.basename(path)
    stdout = r.stdout.decode("utf-8", errors="replace")
    stderr = r.stderr.decode("utf-8", errors="replace")
    print(f"[{name}] rc={r.returncode} elapsed={elapsed:.2f}s")
    if stderr: print(f"  stderr[:200]: {stderr[:200]}")
    if stdout: print(f"  stdout[:200]: {stdout[:200]}")

print(f"Sequential total: {sum(times_seq):.2f}s")
print(f"Concurrent total: {total:.2f}s")
if total > 0:
    print(f"Speedup: {sum(times_seq)/total:.2f}x")
