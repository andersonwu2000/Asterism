import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_flat_concat_ftc_smooth

namespace Problems.residue_thm

-- flat_left_h_contdiff_wrap: ContDiffOn ℝ 1 of the piecewise-FTC primitive on Icc 0 1,
-- delegating to flat_concat_ftc_smooth (unused Q/avoid hypotheses are dropped).
theorem flat_left_h_contdiff_wrap
    {Q : ℂ → ℂ} {a : ℂ}
    (hQ_an : AnalyticOn ℂ Q (Set.univ \ {a}))
    {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContDiffOn ℝ 1
        (fun t : ℝ => α' 0 + ∫ s in (0:ℝ)..t,
          (if s ≤ (1:ℝ)/2
            then 2 * derivWithin α' (Set.Icc 0 1) (2*s)
            else 2 * derivWithin β' (Set.Icc 0 1) (2*s - 1)))
        (Set.Icc 0 1) := by
  exact flat_concat_ftc_smooth hα' hβ' h_match hα'_deriv hβ'_deriv

end Problems.residue_thm
