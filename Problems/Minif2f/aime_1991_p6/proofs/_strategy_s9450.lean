import Mathlib
import Problems.Minif2f.aime_1991_p6.Defs
import Problems.Minif2f.aime_1991_p6.proofs.L_sum_floor_le_545_of_r_lt

namespace Problems.Minif2f.aime_1991_p6

-- Contrapositive decomposition: assume r < 7.43 and derive sum ≤ 545,
-- contradicting h: sum = 546 via `omega`.
-- Sub-goal `sum_floor_le_545_of_r_lt` (Builder) packages the bound:
--   for k ∈ [19,57] (39 terms) `r+k/100 < 8` so `⌊·⌋ ≤ 7`;
--   for k ∈ [58,91] (34 terms) `r+k/100 < 8.34` so `⌊·⌋ ≤ 8`;
--   total ≤ 39·7 + 34·8 = 545.
theorem s9450 :
    ∀ (r : ℝ), (∑ k ∈ Finset.Icc (19 : ℕ) 91, Int.floor (r + k / 100)) = 546 →
      (743 : ℝ)/100 ≤ r := by
  intro r h
  by_contra hlt
  rw [not_le] at hlt
  have h_contra : (∑ k ∈ Finset.Icc (19 : ℕ) 91, Int.floor (r + k / 100)) ≤ 545 :=
    sum_floor_le_545_of_r_lt r hlt
  omega

end Problems.Minif2f.aime_1991_p6
