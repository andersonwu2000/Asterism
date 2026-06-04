import Mathlib
import Problems.Minif2f.mathd_numbertheory_709.Defs
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_card_864_dvd_n
import Problems.Minif2f.mathd_numbertheory_709.proofs.L_n_dvd_864

namespace Problems.Minif2f.mathd_numbertheory_709

-- Split n = 864 into divisibility both ways and combine via Nat.dvd_antisymm.
-- `n_dvd_864`: n divides 864 (bounds prime structure of n from above).
-- `card_864_dvd_n`: 864 divides n (forces 2^5 * 3^3 to divide n).
theorem s9439 : ∀ (n : ℕ) (h₀ : 0 < n) (h₁ : Finset.card (Nat.divisors (2 * n)) = 28) (h₂ : Finset.card (Nat.divisors (3 * n)) = 30), n = 864  := by
  intro n h₀ h₁ h₂
  have h_n_dvd := n_dvd_864 n h₀ h₁ h₂
  have h_dvd_n := card_864_dvd_n n h₀ h₁ h₂
  exact Nat.dvd_antisymm h_n_dvd h_dvd_n

end Problems.Minif2f.mathd_numbertheory_709
