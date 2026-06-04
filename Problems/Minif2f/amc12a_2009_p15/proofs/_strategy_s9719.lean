import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_closed_form_im_mod0

namespace Problems.Minif2f.amc12a_2009_p15

-- Reduce to closed-form: for any n, Im(∑_{k=1}^{4n} k·iᵏ) = -2n.
-- Then m % 4 = 0 ⇒ m = 4·(m/4), giving Im = -2·(m/4) ≤ 0 ≤ 48 trivially.
theorem s9719 : ∀ (m : ℕ), 0 < m → m < 97 → m % 4 = 0 →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).im ≤ 48  := by
  intro m hpos hlt hmod
  have h_closed := closed_form_im_mod0
  have hm4 : m = 4 * (m / 4) := by omega
  rw [hm4, h_closed]
  have hn : (0 : ℝ) ≤ ((m / 4 : ℕ) : ℝ) := by exact_mod_cast Nat.zero_le _
  linarith

end Problems.Minif2f.amc12a_2009_p15
