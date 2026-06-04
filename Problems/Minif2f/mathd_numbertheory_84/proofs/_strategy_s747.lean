import Mathlib
import Problems.Minif2f.mathd_numbertheory_84.Defs

namespace Problems.Minif2f.mathd_numbertheory_84

-- Direct numeric proof: 9/160 * 100 = 5.625, so ⌊5.625⌋ = 5.
-- Reduce via `Int.floor_eq_iff` to the bracketing `5 ≤ 5.625 < 6`; both inequalities
-- discharge by `norm_num` on rational arithmetic. No sub-goals required.
theorem s747 : Int.floor ((9 : ℝ) / 160 * 100) = 5  := by
  apply Int.floor_eq_iff.mpr
  refine ⟨by norm_num, by norm_num⟩

end Problems.Minif2f.mathd_numbertheory_84
