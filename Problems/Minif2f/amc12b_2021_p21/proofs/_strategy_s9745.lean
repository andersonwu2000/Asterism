import Mathlib
import Problems.Minif2f.amc12b_2021_p21.Defs
import Problems.Minif2f.amc12b_2021_p21.proofs.L_ne_above_one
import Problems.Minif2f.amc12b_2021_p21.proofs.L_ne_below_one

namespace Problems.Minif2f.amc12b_2021_p21

-- Decompose no-root on (0, √2) by trichotomy on `y` vs 1:
--   (a) y ∈ (0, 1): LHS = y^(2^√2) < 1 and RHS = √2^(2^y) > 1, hence ≠.
--   (b) y ∈ [1, √2): the narrower analytic case (function-comparison /
--       monotonicity of log y / 2^y) on a strictly smaller interval.
-- Each sub-goal keeps the parent's binders + adds one bound on y, so both
-- are strictly simpler than the parent.
theorem s9745 : ∀ y : ℝ, 0 < y → y < Real.sqrt 2 →
    y ^ (2 : ℝ) ^ Real.sqrt 2 ≠ Real.sqrt 2 ^ (2 : ℝ) ^ y  := by
  intro y hy hy_sqrt2
  rcases lt_or_ge y 1 with hy1 | hy1
  · exact ne_below_one y hy hy_sqrt2 hy1
  · exact ne_above_one y hy hy_sqrt2 hy1

end Problems.Minif2f.amc12b_2021_p21
