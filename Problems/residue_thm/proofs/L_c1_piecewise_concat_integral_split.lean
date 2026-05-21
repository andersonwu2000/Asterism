import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem c1_piecewise_concat_integral_split
    {Q : ℂ → ℂ} {α' β' h : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hh : ContDiffOn ℝ 1 h (Set.Icc 0 1))
    (hh_left : ∀ t ∈ Set.Icc (0 : ℝ) (1/2), h t = α' (2*t))
    (hh_right : ∀ t ∈ Set.Icc (1/2 : ℝ) 1, h t = β' (2*t - 1)) :
    (∫ t in (0 : ℝ)..1, Q (h t) * deriv h t) =
      (∫ t in (0 : ℝ)..1, Q (α' t) * deriv α' t) +
      (∫ t in (0 : ℝ)..1, Q (β' t) * deriv β' t) := by sorry

end Problems.residue_thm
