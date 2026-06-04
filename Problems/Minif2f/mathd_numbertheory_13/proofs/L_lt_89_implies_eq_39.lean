import Mathlib
import Problems.Minif2f.mathd_numbertheory_13.Defs

namespace Problems.Minif2f.mathd_numbertheory_13

-- entry_kind: Builder
theorem lt_89_implies_eq_39 :
    ∀ n : ℕ, 0 < n → 14 * n % 100 = 46 → n < 89 → n = 39 := by omega

end Problems.Minif2f.mathd_numbertheory_13
