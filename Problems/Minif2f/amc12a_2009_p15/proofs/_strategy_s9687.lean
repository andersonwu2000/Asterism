import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_im_mod0
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_im_mod1
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_im_mod2
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_im_mod3

namespace Problems.Minif2f.amc12a_2009_p15

-- Split the parent bound by m % 4, mirroring s9655's residue-class decomposition
-- for the real part. Each sub-goal fixes a single residue mod 4 — strictly
-- simpler than the parent (one residue class instead of all four).
theorem s9687 : ∀ (m : ℕ), 0 < m → m < 97 →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).im ≤ 48  := by
  intro m hpos hlt
  have hcases : m % 4 = 0 ∨ m % 4 = 1 ∨ m % 4 = 2 ∨ m % 4 = 3 := by omega
  rcases hcases with h | h | h | h
  · exact sum_im_mod0 m hpos hlt h
  · exact sum_im_mod1 m hpos hlt h
  · exact sum_im_mod2 m hpos hlt h
  · exact sum_im_mod3 m hpos hlt h

end Problems.Minif2f.amc12a_2009_p15
