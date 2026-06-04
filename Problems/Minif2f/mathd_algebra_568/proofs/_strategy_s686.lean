import Mathlib
import Problems.Minif2f.mathd_algebra_568.Defs

namespace Problems.Minif2f.mathd_algebra_568

-- Pure polynomial identity over ℝ: expand both sides and match coefficients.
-- `ring` discharges this in one step after introducing `a`; no sub-goals needed.
theorem s686 : ∀ (a : ℝ), (a - 1) * (a + 1) * (a + 2) - (a - 2) * (a + 1) = a ^ 3 + a ^ 2  := by
  intro a
  ring


end Problems.Minif2f.mathd_algebra_568
