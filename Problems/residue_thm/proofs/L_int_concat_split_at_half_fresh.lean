import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
theorem int_concat_split_at_half_fresh
    {Q : ℂ → ℂ} {αβ : ℝ → ℂ}
    (hαβ : ContDiffOn ℝ 1 αβ (Set.Icc 0 1)) :
    (∫ t in (0 : ℝ)..1, Q (αβ t) * deriv αβ t) =
      (∫ t in (0 : ℝ)..(1/2), Q (αβ t) * deriv αβ t) +
      (∫ t in ((1/2) : ℝ)..1, Q (αβ t) * deriv αβ t) := by sorry

end Problems.residue_thm
