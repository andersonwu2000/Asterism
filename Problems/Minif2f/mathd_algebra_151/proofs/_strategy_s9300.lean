import Mathlib
import Problems.Minif2f.mathd_algebra_151.Defs
import Problems.Minif2f.mathd_algebra_151.proofs.L_ceil_sqrt_27_eq_six
import Problems.Minif2f.mathd_algebra_151.proofs.L_floor_sqrt_26_eq_five

namespace Problems.Minif2f.mathd_algebra_151

-- Split `⌈√27⌉ - ⌊√26⌋ = 1` into two leaf integer computations.
-- Sub-goals: `ceil_sqrt_27_eq_six` (⌈√27⌉ = 6) and `floor_sqrt_26_eq_five`
-- (⌊√26⌋ = 5). Each is a closed arithmetic fact (no parent binders to thread).
-- Combine by rewriting both into the LHS; `norm_num` closes `6 - 5 = 1`.
theorem s9300 : Int.ceil (Real.sqrt 27) - Int.floor (Real.sqrt 26) = 1  := by
  have h_ceil27 : Int.ceil (Real.sqrt 27) = 6 := ceil_sqrt_27_eq_six
  have h_floor26 : Int.floor (Real.sqrt 26) = 5 := floor_sqrt_26_eq_five
  rw [h_ceil27, h_floor26]
  norm_num

end Problems.Minif2f.mathd_algebra_151
