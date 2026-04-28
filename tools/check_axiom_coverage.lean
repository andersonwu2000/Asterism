/-
  tools/check_axiom_coverage.lean (P6 C42 stub)

  Spec phase6_library.md ## In line 39: `asterism library check-deps`
  wraps a call to this Lean exe. Real exe walks each
  `Library/Theorems/proved.lean` re-export, runs
  `#print axioms <name>`, and reports Problems whose META.md axioms
  don't cover the result.

  STUB (C42): `Tooling/library/check_deps.py` is the operator-facing
  tool in C42 — it performs the same coverage check by reading
  `goals.trust_set` (populated by P3 cascade.build_trust_set). The
  Lean exe is reserved for C44+ when CLI binding ships and the
  strict re-run-#print-axioms path becomes useful (e.g. catching
  trust_set drift on Mathlib upgrades).
-/

import Lean

-- TODO C44+: real implementation walks Library + emits JSONL
def main : IO Unit := do
  IO.eprintln "check_axiom_coverage.lean: stub (P6 C44+)"
  IO.eprintln "use `asterism library check-deps` for now"
