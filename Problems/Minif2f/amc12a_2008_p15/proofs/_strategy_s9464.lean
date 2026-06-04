import Mathlib
import Problems.Minif2f.amc12a_2008_p15.Defs

namespace Problems.Minif2f.amc12a_2008_p15

-- Direct proof reusing the periodic lemma 2^(4k+4) ≡ 6 (mod 10).
-- Inline an induction on k (base 2^4 = 16, step pow_add + Nat.mul_mod),
-- then express m as 4*(m/4 - 1) + 4 via omega and apply.
theorem s9464 : ∀ (m : ℕ),
    m % 10 = 0 → m % 4 = 0 → 4 ≤ m → 2 ^ m % 10 = 6  := by
  intro m _hm10 hm4 hm_ge
  have h_period : ∀ (k : ℕ), 2 ^ (4 * k + 4) % 10 = 6 := by
    intro k
    induction k with
    | zero => norm_num
    | succ k ih =>
      have h : 4 * (k + 1) + 4 = (4 * k + 4) + 4 := by ring
      rw [h, pow_add, Nat.mul_mod, ih]
      norm_num
  have heq : m = 4 * (m / 4 - 1) + 4 := by omega
  rw [heq]
  exact h_period (m / 4 - 1)

end Problems.Minif2f.amc12a_2008_p15
