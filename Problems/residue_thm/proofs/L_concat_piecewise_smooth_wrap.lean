import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem concat_piecewise_smooth_wrap
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContDiffOn ℝ 1
        (fun t : ℝ => if t ≤ (1:ℝ)/2 then α' (2*t) else β' (2*t - 1))
        (Set.Icc 0 1) := by sorry

end Problems.residue_thm
