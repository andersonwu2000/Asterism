import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_closed_form_re_mod1

namespace Problems.Minif2f.amc12a_2009_p15

-- Prove the closed form Re(S_m) = (m-1)/2 for m ≡ 1 mod 4, then conclude:
-- m > 97 ∧ m % 4 = 1 forces m ≥ 101 (the smallest such), so (m-1)/2 ≥ 50.
theorem s9696 : ∀ (m : ℕ), 97 < m → m % 4 = 1 →
    50 ≤ (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).re  := by
  intro m hgt hmod
  have h_cf := closed_form_re_mod1 m (by omega) hmod
  rw [h_cf]
  have hm : 101 ≤ m := by omega
  have hmR : (101 : ℝ) ≤ (m : ℝ) := by exact_mod_cast hm
  linarith

end Problems.Minif2f.amc12a_2009_p15
