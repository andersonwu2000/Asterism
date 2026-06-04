import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_closed_form_re_mod0

namespace Problems.Minif2f.amc12a_2009_p15

-- Reduce to the closed-form: for any n, Re ∑_{k=1}^{4n} k·iᵏ = 2n.
-- Then m > 97 ∧ m ≡ 0 (mod 4) ⇒ m = 4·(m/4) with m/4 ≥ 25, giving Re ≥ 50.
theorem s9695 : ∀ (m : ℕ), 97 < m → m % 4 = 0 →
    50 ≤ (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).re  := by
  intro m hm hmod
  have h_closed := closed_form_re_mod0
  have hm4 : m = 4 * (m / 4) := by omega
  have hge : 25 ≤ m / 4 := by omega
  rw [hm4, h_closed]
  have hc : (25 : ℝ) ≤ ((m / 4 : ℕ) : ℝ) := by exact_mod_cast hge
  linarith

end Problems.Minif2f.amc12a_2009_p15
