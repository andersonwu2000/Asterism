import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs
import Problems.Minif2f.amc12a_2008_p15.proofs.L_two_pow_four_k_plus_four_mod_ten

namespace Problems.Minif2f.amc12a_2008_p15

-- Decompose `2^m % 10 = 6` (for m % 4 = 0, 4 ≤ m) into a single periodic lemma:
-- ∀ k, 2^(4*k + 4) % 10 = 6 (provable by induction on k, base 2^4 = 16 % 10 = 6, step uses
-- pow_add + Nat.mul_mod). From m % 4 = 0 and 4 ≤ m, omega gives m = 4*(m/4 - 1) + 4,
-- and we apply the periodic lemma at k = m/4 - 1. Hypothesis hm10 is unused (parent over-supplies).
theorem s9452 : ∀ (m : ℕ),
    m % 10 = 0 → m % 4 = 0 → 4 ≤ m → 2^m % 10 = 6  := by
  intro m hm10 hm4 hm_ge
  have h_period := two_pow_four_k_plus_four_mod_ten
  have heq : m = 4 * (m / 4 - 1) + 4 := by omega
  rw [heq]
  exact h_period (m / 4 - 1)

end Problems.Minif2f.amc12a_2008_p15
