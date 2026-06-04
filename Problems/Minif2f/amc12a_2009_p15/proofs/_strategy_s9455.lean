import Mathlib
import Problems.Minif2f.amc12a_2009_p15.Defs
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_at_97_closed_form
import Problems.Minif2f.amc12a_2009_p15.proofs.L_sum_below_97_neq_target

namespace Problems.Minif2f.amc12a_2009_p15

-- Rewrite the RHS to its closed-form value `48 + 49 * I` via `sum_at_97_closed_form`,
-- reducing the goal to "no m ∈ (0, 97) yields the same closed form" — `sum_below_97_neq_target`.
-- Both sub-goals are computationally bounded (single closed value vs. finite case-split)
-- and avoid relating two indexed sums directly.
theorem s9455 : ∀ (m : ℕ), 0 < m → m < 97 →
    (∑ k ∈ Finset.Icc (1 : ℕ) m, (↑k : ℂ) * Complex.I ^ k) ≠
    (∑ k ∈ Finset.Icc (1 : ℕ) 97, (↑k : ℂ) * Complex.I ^ k)  := by
  intro m hm hmlt
  have h_at_97 := sum_at_97_closed_form
  have h_below := sum_below_97_neq_target
  rw [h_at_97]
  exact h_below m hm hmlt

end Problems.Minif2f.amc12a_2009_p15
