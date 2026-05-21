import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem residue_thm_reduction
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hsc : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmap : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    (h_radius : ∀ a ∈ T, ∃ R : ℝ, 0 < R ∧ AnalyticOn ℂ f (Metric.ball a R \ {a}))
    (h_winding : ∀ a ∈ T, ∃ k : ℤ,
        (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 2 * Real.pi * Complex.I * k) :
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 2 * Real.pi * Complex.I *
      ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * Complex.residue f a := by sorry

end Problems.residue_thm
