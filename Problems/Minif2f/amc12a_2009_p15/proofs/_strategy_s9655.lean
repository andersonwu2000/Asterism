import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_re_mod0
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_re_mod1
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_re_mod2
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_re_mod3

namespace Problems.Minif2f.amc12a_2009_p15

-- Split the (-50, 50) dichotomy by m % 4. Each residue class has a fixed
-- single-sided bound: m ≡ 0, 1 give Re ≥ 50; m ≡ 2, 3 give Re ≤ -50.
-- Each sub-goal is a single inequality (no disjunction) on a fixed residue,
-- strictly simpler than the parent dichotomy.
theorem s9655 : ∀ (m : ℕ), 97 < m →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).re ≤ -50 ∨
    50 ≤ (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k).re  := by
  intro m hm
  have hcases : m % 4 = 0 ∨ m % 4 = 1 ∨ m % 4 = 2 ∨ m % 4 = 3 := by omega
  rcases hcases with h | h | h | h
  · exact Or.inr (sum_re_mod0 m hm h)
  · exact Or.inr (sum_re_mod1 m hm h)
  · exact Or.inl (sum_re_mod2 m hm h)
  · exact Or.inl (sum_re_mod3 m hm h)

end Problems.Minif2f.amc12a_2009_p15
