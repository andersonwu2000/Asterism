import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Builder
-- primitive_comp_path_continuous_on: ContinuousOn (F ∘ γ) on Icc a b
-- via HasDerivAt → ContinuousAt for F, ContDiffOn.continuousOn for γ, MapsTo for composition.
theorem primitive_comp_path_continuous_on
    {f F : ℂ → ℂ} {z₀ : ℂ} {R : ℝ} {γ : ℝ → ℂ} {a b : ℝ}
    (hab : a ≤ b)
    (hF : ∀ z ∈ Metric.ball z₀ R, HasDerivAt F (f z) z)
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc a b))
    (hγU : Set.MapsTo γ (Set.Icc a b) (Metric.ball z₀ R)) :
    ContinuousOn (fun t => F (γ t)) (Set.Icc a b) := by
  have hγcont : ContinuousOn γ (Set.Icc a b) := hγ.continuousOn
  have hFcont : ContinuousOn F (Metric.ball z₀ R) := by
    intro z hz
    exact (hF z hz).continuousAt.continuousWithinAt
  exact hFcont.comp hγcont hγU

end Problems.residue_thm
