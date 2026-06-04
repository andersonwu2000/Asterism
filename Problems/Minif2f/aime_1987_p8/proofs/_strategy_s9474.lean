import Mathlib
import Problems.Minif2f.aime_1987_p8.Defs
import Problems.Minif2f.aime_1987_p8.proofs.L_gt_96_of_upper_bound
import Problems.Minif2f.aime_1987_p8.proofs.L_lt_98_of_lower_bound

namespace Problems.Minif2f.aime_1987_p8

-- Clear denominators on each bound separately, reducing to integer bounds on y.
-- `lt_98_of_lower_bound`: 8/15 < 112/(112+y) → y < 98 (cross-multiply).
-- `gt_96_of_upper_bound`: 112/(112+y) < 7/13 → 96 < y (cross-multiply).
-- Combined: 96 < y < 98 → y = 97 by `omega`.
theorem s9474 : ∀ y : ℕ, ((8 : ℝ) / 15 < (112 : ℝ) / (112 + y)
    ∧ (112 : ℝ) / (112 + y) < 7 / 13) → y = 97  := by
  intro y h
  have h1 : y < 98 := lt_98_of_lower_bound y h.1
  have h2 : 96 < y := gt_96_of_upper_bound y h.2
  omega

end Problems.Minif2f.aime_1987_p8
