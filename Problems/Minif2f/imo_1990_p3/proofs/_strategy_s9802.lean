import Mathlib
import Problems.Minif2f.imo_1990_p3.Defs
import Problems.Minif2f.imo_1990_p3.proofs.L_cube_factor
import Problems.Minif2f.imo_1990_p3.proofs.L_three_dvd_quad

namespace Problems.Minif2f.imo_1990_p3

-- Factorize `a^3 + 1 = (a+1) * (a^2 - a + 1)`, then split divisibility:
--   `3^(n+1) ∣ a+1` (parent hypothesis) and `3 ∣ a^2 - a + 1` (mod-3 arithmetic
--   from `3 ∣ a+1`).  Multiplying gives `3^(n+2) = 3^(n+1) * 3 ∣ a^3 + 1`.
-- Sub-goal `cube_factor` drops `n` and the divisibility hypothesis (pure ring
-- identity in ℕ with subtraction).  Sub-goal `three_dvd_quad` drops `n` and the
-- `1 ≤ a` premise (mod-3 argument on `a+1 ≡ 0`).
theorem s9802 : ∀ (a n : ℕ), 1 ≤ a → 3^(n+1) ∣ a + 1 → 3^(n+2) ∣ a^3 + 1  := by
  intro a n ha hdvd
  have hfact : a^3 + 1 = (a + 1) * (a^2 - a + 1) := cube_factor a ha
  have hsmall : (3 : ℕ) ∣ a + 1 :=
    dvd_trans (dvd_pow_self 3 (Nat.succ_ne_zero n)) hdvd
  have h3 : 3 ∣ a^2 - a + 1 := three_dvd_quad a hsmall
  rw [hfact, pow_succ]
  exact Nat.mul_dvd_mul hdvd h3

end Problems.Minif2f.imo_1990_p3
