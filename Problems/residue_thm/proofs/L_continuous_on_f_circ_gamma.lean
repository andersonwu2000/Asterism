import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- continuous_on_f_circ_gamma: F∘γ continuous on [0,1] — F continuous from HasDerivAt,
-- γ continuous from ContDiffOn, composed via ContinuousOn.comp.
theorem continuous_on_f_circ_gamma
    {U : Set ℂ} {f F : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U)
    (hF : ∀ z ∈ U, HasDerivAt F (f z) z)
    (hγC1 : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) U) :
    ContinuousOn (fun t => F (γ t)) (Set.Icc (0:ℝ) 1) := by
  have hFcont : ContinuousOn F U := fun z hz => (hF z hz).continuousAt.continuousWithinAt
  have hγcont : ContinuousOn γ (Set.Icc 0 1) := hγC1.continuousOn
  exact hFcont.comp hγcont hγU

end Problems.residue_thm
