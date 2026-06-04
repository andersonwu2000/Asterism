-- Set `k := Nat.sqrt (10*b+6)`, so `h₁ : k*k = 10*b+6`. From `b < 10` we get
-- `10*b+6 ≤ 96 < 100`, hence `k < 10` (else `k*k ≥ 100`). `interval_cases k`
-- splits into ten concrete `k = c` cases; in each, `h₁` becomes `c*c = 10*b+6`,
-- a linear constraint that `omega` resolves (k∈{4,6} ⇒ b∈{1,3}, others ⇒ ⊥).
-- Kernel-only — no `native_decide`, no rogue axioms.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_22.Defs
import Problems.Minif2f.mathd_numbertheory_22.proofs._strategy_s707

namespace Problems.Minif2f.mathd_numbertheory_22

def main := @Problems.Minif2f.mathd_numbertheory_22.s707

end Problems.Minif2f.mathd_numbertheory_22
