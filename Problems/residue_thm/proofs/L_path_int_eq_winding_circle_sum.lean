import Mathlib
import Problems.residue_thm.Defs

namespace Problems.residue_thm

-- entry_kind: Backward
theorem path_int_eq_winding_circle_sum
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hsc : SimplyConnectedSpace ↥U)
    (hT : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγ : ContDiffOn ℝ 1 γ (Set.Icc 0 1))
    (hmaps : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T))
    (hclosed : γ 0 = γ 1)
    {r ρ : ℂ → ℝ}
    (hρ_pos : ∀ a ∈ T, 0 < ρ a)
    (hρ_lt : ∀ a ∈ T, ρ a < r a)
    (hr_analytic : ∀ a ∈ T, AnalyticOn ℂ f (Metric.ball a (r a) \ {a}))
    (hρ_path : ∀ a ∈ T, Disjoint (Metric.closedBall a (ρ a)) (γ '' Set.Icc (0 : ℝ) 1))
    (hρ_pairwise : ∀ a ∈ T, ∀ b ∈ T, a ≠ b →
        Disjoint (Metric.closedBall a (ρ a)) (Metric.closedBall b (ρ b))) :
    (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) =
      ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * ∮ z in C(a, ρ a), f z := by sorry

end Problems.residue_thm
