"""
spike-001: Test concurrent lake env lean subprocess calls for cache lock conflicts.
Run from /d/Hadamard directory.
"""
import subprocess
import threading
import time
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

HADAMARD_DIR = "D:\\Hadamard"
SPIKE_DIR = os.path.dirname(os.path.abspath(__file__))

files = [
    f"{SPIKE_DIR}/spike001_a.lean",
    f"{SPIKE_DIR}/spike001_b.lean",
    f"{SPIKE_DIR}/spike001_c.lean",
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
            timeout=120,
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

print("=== spike-001: concurrent lake env lean test ===")
print(f"Running {len(files)} concurrent subprocesses...")

threads = [threading.Thread(target=run_lean, args=(f,)) for f in files]
t_start = time.time()
for t in threads:
    t.start()
for t in threads:
    t.join()
total = time.time() - t_start

print(f"Total wall-clock: {total:.2f}s")
print()

ok = True
for path, res in results.items():
    name = os.path.basename(path)
    rc = res["returncode"]
    elapsed = res["elapsed"]
    print(f"[{name}] rc={rc} elapsed={elapsed:.2f}s")
    if res["stderr"]:
        print(f"  stderr: {res['stderr'][:200]}")
    if res["stdout"]:
        print(f"  stdout: {res['stdout'][:200]}")
    if rc != 0:
        ok = False

for path, err in errors.items():
    print(f"[ERROR] {path}: {err}")
    ok = False

print()
print("RESULT:", "PASS - no conflicts detected" if ok else "FAIL - errors occurred")

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
        timeout=120,
    )
    elapsed = time.time() - start
    times_seq.append(elapsed)
    name = os.path.basename(path)
    stdout = r.stdout.decode("utf-8", errors="replace")
    stderr = r.stderr.decode("utf-8", errors="replace")
    print(f"[{name}] rc={r.returncode} elapsed={elapsed:.2f}s")
    if stderr: print(f"  stderr: {stderr[:300]}")
    if stdout: print(f"  stdout: {stdout[:300]}")

print(f"Sequential total: {sum(times_seq):.2f}s")
print(f"Concurrent total: {total:.2f}s")
print(f"Speedup: {sum(times_seq)/total:.2f}x")
