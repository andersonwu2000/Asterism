import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_neq_above_97
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_neq_below_97

namespace Problems.Minif2f.amc12a_2009_p15

-- Trichotomy on `m` vs `97`: m < 97 / m = 97 / m > 97. The equal branch closes
-- directly; the two non-equal branches contradict h₁ via dedicated sub-lemmas
-- `sum_neq_below_97` (finite case-split, 0 < m < 97) and `sum_neq_above_97`
-- (uses closed-form / magnitude growth of the partial sum for m > 97).
theorem s9349 : ∀ (m : ℕ) (_h₀ : 0 < m)
    (_h₁ : (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k) =
      (∑ k ∈ Finset.Icc (1 : ℕ) 97, (↑k : ℂ) * Complex.I ^ k)),
    m = 97  := by
  intro m h₀ h₁
  have h_below := sum_neq_below_97
  have h_above := sum_neq_above_97
  rcases lt_trichotomy m 97 with hlt | heq | hgt
  · exact absurd h₁ (h_below m h₀ hlt)
  · exact heq
  · exact absurd h₁ (h_above m hgt)

end Problems.Minif2f.amc12a_2009_p15
