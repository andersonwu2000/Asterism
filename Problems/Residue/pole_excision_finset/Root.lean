import Mathlib
import Problems.Residue.pole_excision_finset.Defs

namespace Problems.Residue.pole_excision_finset

theorem main : ∀ {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ} {r : ℂ → ℝ},
  IsOpen U → SimplyConnectedSpace ↥U →
  (∀ a ∈ T, a ∈ U) →
  AnalyticOn ℂ f (U \ ↑T) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T) →
  γ 0 = γ 1 →
  (∀ a ∈ T, 0 < r a) →
  (∀ a ∈ T, Metric.closedBall a (r a) ⊆ U) →
  (∀ a ∈ T, ∀ b ∈ T, b ≠ a → b ∉ Metric.closedBall a (r a)) →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) -
    ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) *
      (∮ z in C(a, r a), f z) = 0 := by sorry

end Problems.Residue.pole_excision_finset
