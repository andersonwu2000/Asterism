import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- h_deriv_gamma_sub_dw: DifferentiableWithinAt.hasDerivWithinAt + sub_const closes the goal;
-- uses ContDiffOn.differentiableOn to get DifferentiableWithinAt at s ∈ Ico 0 1 ⊆ Icc 0 1.
theorem h_deriv_gamma_sub_dw
    {γ : ℝ → ℂ} {a : ℂ}
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hclosed : γ 0 = γ 1)
    (havoid : ∀ t ∈ Set.Icc (0 : ℝ) 1, γ t ≠ a) :
    ∀ s ∈ Set.Ico (0 : ℝ) 1,
      HasDerivWithinAt (fun s => γ s - a)
        (derivWithin γ (Set.Icc (0 : ℝ) 1) s) (Set.Icc (0 : ℝ) 1) s := by
  intro s hs
  have hdiff := hγ.differentiableOn (by norm_num) s (Set.Ico_subset_Icc_self hs)
  exact hdiff.hasDerivWithinAt.sub_const a

end Problems.residue_thm
