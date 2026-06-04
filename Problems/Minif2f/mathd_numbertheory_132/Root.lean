-- Closed-form numeric fact: 2004 = 12 * 167, so 2004 % 12 = 0.
-- No hypotheses, no binders — pure `Nat` literal arithmetic.
-- `decide` kernel-reduces both sides to `0` (Lean's `Nat.mod` is decidable on literals); leaf-bypass.
import Mathlib
import Problems.Minif2f.mathd_numbertheory_132.Defs
import Problems.Minif2f.mathd_numbertheory_132.proofs._strategy_s696

namespace Problems.Minif2f.mathd_numbertheory_132

def main := @Problems.Minif2f.mathd_numbertheory_132.s696

end Problems.Minif2f.mathd_numbertheory_132
