import Mathlib
import Problems.Minif2f.mathd_numbertheory_132.Defs

namespace Problems.Minif2f.mathd_numbertheory_132

-- Closed-form numeric fact: 2004 = 12 * 167, so 2004 % 12 = 0.
-- No hypotheses, no binders — pure `Nat` literal arithmetic.
-- `decide` kernel-reduces both sides to `0` (Lean's `Nat.mod` is decidable on literals); leaf-bypass.
theorem s696 : 2004 % 12 = 0  := by decide

end Problems.Minif2f.mathd_numbertheory_132
