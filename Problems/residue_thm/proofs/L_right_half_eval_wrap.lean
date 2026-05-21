import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_flat_concat_right_half_piecewise_eval

namespace Problems.residue_thm

-- entry_kind: Builder
theorem right_half_eval_wrap
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ∀ t ∈ Set.Icc ((1:ℝ)/2) 1,
      (∫ s in ((1:ℝ)/2:ℝ)..t,
        (if s ≤ (1:ℝ)/2
          then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
          else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        = β' (2*t - 1) - β' 0 :=
  flat_concat_right_half_piecewise_eval hα' hβ' h_match hα'_deriv hβ'_deriv

end Problems.residue_thm
