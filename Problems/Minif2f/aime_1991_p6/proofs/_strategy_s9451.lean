import Mathlib
import Problems.Minif2f.aime_1991_p6.Defs
import Problems.Minif2f.aime_1991_p6.proofs.L_sum_floor_geq_547

namespace Problems.Minif2f.aime_1991_p6

-- Contrapositive: assume 744/100 ≤ r, then sum at r ≥ sum at 744/100 = 547.
-- Sub-goal: pure lower bound (no `=546` hypothesis). Combined with h_sum=546, linarith.
theorem s9451 : ∀ (r : ℝ), (∑ k ∈ Finset.Icc (19 : ℕ) 91, Int.floor (r + k / 100)) = 546 → r < 744/100  := by
  intro r h_sum
  by_contra h_neg
  push_neg at h_neg
  have h_lb := sum_floor_geq_547 r h_neg
  linarith

end Problems.Minif2f.aime_1991_p6
