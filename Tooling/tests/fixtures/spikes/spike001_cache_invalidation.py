"""
spike-001 extension: verify lake re-elaborates same-path .lean when content changes.

Builder's tactic_try loop overwrites the same staging .lean for each tactic and re-runs
`lake env lean`. If lake hits a stale cache (no real elab), the loop would falsely
report pass — entire P1 demo would be a false positive.

Test: write file with passing tactic, verify pass; overwrite SAME path with failing
tactic, re-run, verify fail. If second run still passes, cache is content-blind for
this path.
"""
import subprocess
import time
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

HADAMARD = "D:\\Hadamard"
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spike001_cache_inv.lean")

PASS_BODY = """-- spike-001 ext: pass body — 1+1=2
theorem cache_inv_test : 1 + 1 = 2 := by decide
"""
FAIL_BODY = """-- spike-001 ext: fail body — 1+1=3 (simp/decide can't prove false)
theorem cache_inv_test : 1 + 1 = 3 := by decide
"""


def run_lean(label):
    start = time.time()
    r = subprocess.run(
        ["lake", "env", "lean", PATH],
        cwd=HADAMARD,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
    )
    elapsed = time.time() - start
    print(f"[{label}] rc={r.returncode} elapsed={elapsed:.2f}s")
    out = r.stdout.decode("utf-8", errors="replace").strip()
    err = r.stderr.decode("utf-8", errors="replace").strip()
    if out:
        print(f"  stdout: {out[:300]}")
    if err:
        print(f"  stderr: {err[:300]}")
    return r.returncode


print("=== spike-001 extension: cache invalidation when same path content changes ===")
print(f"Path: {PATH}")
print()

# Round 1: pass body
with open(PATH, "w", encoding="utf-8") as f:
    f.write(PASS_BODY)
print("[round 1] wrote PASS body (1+1=2 by decide)")
rc1 = run_lean("round 1")

# Round 2: fail body, SAME path
with open(PATH, "w", encoding="utf-8") as f:
    f.write(FAIL_BODY)
print("[round 2] OVERWROTE same path with FAIL body (1+1=3 by decide)")
rc2 = run_lean("round 2")

# Round 3: pass body again
with open(PATH, "w", encoding="utf-8") as f:
    f.write(PASS_BODY)
print("[round 3] OVERWROTE same path back with PASS body (1+1=2 by decide)")
rc3 = run_lean("round 3")

print()
print(f"Result: rc1={rc1} (expect 0), rc2={rc2} (expect 1), rc3={rc3} (expect 0)")
if rc1 == 0 and rc2 != 0 and rc3 == 0:
    print("PASS — cache invalidation works: lake re-elaborates per content")
else:
    print("FAIL — cache may be content-blind for same path; Builder tactic_try unsafe")

# cleanup test file
try:
    os.remove(PATH)
except OSError:
    pass
