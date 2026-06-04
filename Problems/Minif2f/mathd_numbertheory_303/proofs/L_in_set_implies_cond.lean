import Mathlib
import Problems.Minif2f.mathd_numbertheory_303.Defs

namespace Problems.Minif2f.mathd_numbertheory_303

-- entry_kind: Builder
theorem in_set_implies_cond :
    ∀ n : ℕ, (n = 7 ∨ n = 13 ∨ n = 91) →
      (2 ≤ n ∧ 171 ≡ 80 [MOD n] ∧ 468 ≡ 13 [MOD n]) := by norm_num

end Problems.Minif2f.mathd_numbertheory_303
