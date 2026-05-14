"""Spike Option C: keep worker alive, swap file content via didChange.

Key question: does swapping content via didChange (same URI) reuse the
worker's Mathlib namespace state and cost less than the ~27s fresh
didOpen?

Plan:
  1. didOpen URI X with `import Mathlib` (warmup) → measure cold cost
  2. didChange URI X to a real-ish proof body → measure
  3. didChange URI X to another proof body → measure
  4. Compare to baseline 27s fresh-worker cost
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, ".")
from Tooling.lsp.client import LspClient


WARMUP = "import Mathlib\n"

PROOF_A = """import Mathlib

open Real

theorem swap_test_a (x : ℝ) (hx : 0 ≤ x) : 0 ≤ x * x := by
  nlinarith [sq_nonneg x]
"""

PROOF_B = """import Mathlib

open Real

theorem swap_test_b (a b : ℝ) (ha : 0 ≤ a) (hb : 0 ≤ b) :
    0 ≤ a * b := by
  exact mul_nonneg ha hb
"""

PROOF_C = """import Mathlib

open Finset BigOperators

theorem swap_test_c (n : ℕ) : ∑ i ∈ range n, (1 : ℕ) = n := by
  simp
"""


def wait_settled(c: LspClient, uri: str, max_wait: float = 120) -> float:
    t0 = time.perf_counter()
    try:
        c.wait_for_file_done(uri, timeout=max_wait)
    except TimeoutError:
        pass
    c.wait_for_diagnostics_settled(uri, stable_for=3.0,
                                    max_wait=max_wait)
    return time.perf_counter() - t0


def main() -> None:
    ws = Path("D:/Asterism")
    c = LspClient(ws)
    c.start()
    c.initialize(timeout=60)

    slot = ws / "_spike_slot.lean"
    slot.write_text(WARMUP, encoding="utf-8")
    uri = slot.as_uri()

    # Step 1: didOpen with warmup (cold start, baseline ~27s)
    t = time.perf_counter()
    c.did_open(slot, WARMUP)
    elapsed = wait_settled(c, uri)
    print(f"[1] didOpen warmup            : {elapsed:.1f}s")

    # Step 2: didChange to PROOF_A
    c.clear_diagnostics(uri)
    slot.write_text(PROOF_A, encoding="utf-8")
    t = time.perf_counter()
    c.did_change_full(slot, PROOF_A, version=2)
    elapsed = wait_settled(c, uri)
    print(f"[2] didChange → proof A       : {elapsed:.1f}s")

    # Step 3: didChange to PROOF_B
    c.clear_diagnostics(uri)
    slot.write_text(PROOF_B, encoding="utf-8")
    t = time.perf_counter()
    c.did_change_full(slot, PROOF_B, version=3)
    elapsed = wait_settled(c, uri)
    print(f"[3] didChange → proof B       : {elapsed:.1f}s")

    # Step 4: didChange to PROOF_C (different namespaces)
    c.clear_diagnostics(uri)
    slot.write_text(PROOF_C, encoding="utf-8")
    t = time.perf_counter()
    c.did_change_full(slot, PROOF_C, version=4)
    elapsed = wait_settled(c, uri)
    print(f"[4] didChange → proof C       : {elapsed:.1f}s")

    # Step 5: didChange back to warmup (idle return)
    c.clear_diagnostics(uri)
    slot.write_text(WARMUP, encoding="utf-8")
    c.did_change_full(slot, WARMUP, version=5)
    elapsed = wait_settled(c, uri)
    print(f"[5] didChange → warmup        : {elapsed:.1f}s")

    slot.unlink(missing_ok=True)
    c.shutdown()


if __name__ == "__main__":
    main()
