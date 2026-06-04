import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_closed_form_im_mod1

namespace Problems.Minif2f.amc12a_2009_p15

-- Reduce the residue-1 bound to one closed-form sub-goal:
-- `(∑ k∈Icc 1 (4n+1), k*I^k).im = 2n+1`. With `m = 4(m/4)+1` (omega
-- from `m%4=1`), rewriting m makes the parent goal `2*(m/4)+1 ≤ 48`,
-- which `linarith` closes from `m/4 ≤ 23` (since `m < 97`).
theorem s9720 : ∀ (m : ℕ), 0 < m → m < 97 → m % 4 = 1 →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).im ≤ 48  := by
  intro m hm hm97 hmod
  have h_closed := closed_form_im_mod1
  have hm4 : m = 4 * (m / 4) + 1 := by omega
  rw [hm4, h_closed]
  have hbound : ((m / 4 : ℕ) : ℝ) ≤ 23 := by
    exact_mod_cast (by omega : m / 4 ≤ 23)
  linarith

end Problems.Minif2f.amc12a_2009_p15
