import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_piecewise_concat_derivwithin_continuous
import Problems.residue_thm.proofs.L_piecewise_concat_differentiable_on

namespace Problems.residue_thm

-- Reduce `ContDiffOn ℝ 1` on `Icc 0 1` to its `contDiffOn_one_iff_derivWithin`
-- pair: pointwise differentiability + continuity of the within-derivative.
-- Both pieces reuse the parent's hypotheses unchanged; the closer is the
-- Mathlib equivalence applied with `uniqueDiffOn_Icc zero_lt_one`. Each
-- sub-goal is strictly weaker than the parent C¹ statement.
theorem s10572
    {a : ℂ} {α' β' : ℝ → ℂ}
    (hα' : ContDiffOn ℝ 1 α' (Set.Icc 0 1))
    (hα'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, α' t ≠ a)
    (hβ' : ContDiffOn ℝ 1 β' (Set.Icc 0 1))
    (hβ'_avoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, β' t ≠ a)
    (h_match : α' 1 = β' 0)
    (hα'_deriv : derivWithin α' (Set.Icc 0 1) 1 = 0)
    (hβ'_deriv : derivWithin β' (Set.Icc 0 1) 0 = 0) :
    ContDiffOn ℝ 1 (fun t : ℝ => if t ≤ 1/2 then α' (2*t) else β' (2*t - 1))
      (Set.Icc 0 1)  := by
  have h_diff := piecewise_concat_differentiable_on
    hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  have h_deriv_cont := piecewise_concat_derivwithin_continuous
    hα' hα'_avoid hβ' hβ'_avoid h_match hα'_deriv hβ'_deriv
  exact (contDiffOn_one_iff_derivWithin (uniqueDiffOn_Icc zero_lt_one)).mpr
    ⟨h_diff, h_deriv_cont⟩

end Problems.residue_thm
