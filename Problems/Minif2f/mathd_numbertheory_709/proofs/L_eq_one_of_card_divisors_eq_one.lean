import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs

namespace Problems.Minif2f.mathd_numbertheory_709

-- entry_kind: Builder
theorem eq_one_of_card_divisors_eq_one :
    ∀ (r : ℕ), 0 < r → Finset.card (Nat.divisors r) = 1 → r = 1 := by norm_num

end Problems.Minif2f.mathd_numbertheory_709
