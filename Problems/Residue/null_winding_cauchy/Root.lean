import Mathlib
import Problems.Residue.null_winding_cauchy.Defs

namespace Problems.Residue.null_winding_cauchy

theorem main : ∀ {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ},
  IsOpen U → SimplyConnectedSpace ↥U →
  (∀ a ∈ T, a ∈ U) →
  AnalyticOn ℂ f (U \ ↑T) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T) →
  γ 0 = γ 1 →
  (∀ a ∈ T, Complex.windingNumber γ a = 0) →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 0 := by sorry

end Problems.Residue.null_winding_cauchy
