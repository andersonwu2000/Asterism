import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs

namespace Problems.Minif2f.mathd_numbertheory_709

-- entry_kind: Backward
theorem card_864_dvd_n : ∀ (n : ℕ) (h₀ : 0 < n) (h₁ : Finset.card (Nat.divisors (2 * n)) = 28) (h₂ : Finset.card (Nat.divisors (3 * n)) = 30), (864 : ℕ) ∣ n := by sorry

end Problems.Minif2f.mathd_numbertheory_709
