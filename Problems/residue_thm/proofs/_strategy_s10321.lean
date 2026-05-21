import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_exists_inner_radii_disjoint
import Problems.residue_thm.proofs.L_exists_outer_radii_analyticity

namespace Problems.residue_thm

-- Decomposition: first produce per-pole outer radii r — positivity and
-- AnalyticOn on the punctured disk — from openness of U and discreteness of T
-- inside U; then shrink to inner radii ρ ∈ (0, r) simultaneously disjoint from
-- γ's compact image and pairwise disjoint between distinct poles.
theorem s10321
    {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ}
    (hU : IsOpen U) (hTU : ∀ a ∈ T, a ∈ U)
    (hf : AnalyticOn ℂ f (U \ ↑T))
    (hγC : ContinuousOn γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T)) :
    ∃ r ρ : ℂ → ℝ,
      (∀ a ∈ T, 0 < ρ a) ∧
      (∀ a ∈ T, ρ a < r a) ∧
      (∀ a ∈ T, AnalyticOn ℂ f (Metric.ball a (r a) \ {a})) ∧
      (∀ a ∈ T, Disjoint (Metric.closedBall a (ρ a)) (γ '' Set.Icc (0:ℝ) 1)) ∧
      (∀ a ∈ T, ∀ b ∈ T, a ≠ b →
        Disjoint (Metric.closedBall a (ρ a)) (Metric.closedBall b (ρ b))) := by
  obtain ⟨r, hr_pos, hr_analytic⟩ :=
    exists_outer_radii_analyticity hU hTU hf
  obtain ⟨ρ, hρ_pos, hρ_lt, hρ_path, hρ_pairwise⟩ :=
    exists_inner_radii_disjoint (U := U) r hr_pos hγC hγU
  exact ⟨r, ρ, hρ_pos, hρ_lt, hr_analytic, hρ_path, hρ_pairwise⟩

end Problems.residue_thm
