import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem int_h_split_at_half
    {Q : ℂ → ℂ} {h : ℝ → ℂ}
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1)) :
    (∫ t in (0 : ℝ)..1, Q (h t) * deriv h t) =
      (∫ t in (0 : ℝ)..(1/2), Q (h t) * deriv h t) +
      (∫ t in ((1/2) : ℝ)..1, Q (h t) * deriv h t) := by sorry

end Problems.residue_thm
