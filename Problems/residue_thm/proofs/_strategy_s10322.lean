import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_infdist_gamma_image_pos
import Problems.residue_thm.proofs.L_pairwise_pole_lower_bound

namespace Problems.residue_thm

-- Decomposition: build ρ from (a) per-pole positivity of infDist to γ's compact
-- image (analytic content: compactness + γ avoiding T) and (b) a uniform positive
-- lower bound on pairwise distances inside T (pure Finset combinatorics).
-- Set ρ a := min (r a / 2) (min (infDist a (γ '' [0,1]) / 2) (d / 4)). Each of
-- the four conjuncts (positivity, < r, γ-disjointness via
-- disjoint_closedBall_of_lt_infDist, pairwise via closedBall_disjoint_closedBall)
-- follows from ρ a ≤ the corresponding ingredient.
theorem s10322
    {U : Set ℂ} {T : Finset ℂ} {γ : ℝ → ℂ} (r : ℂ → ℝ)
    (hr_pos : ∀ a ∈ T, 0 < r a)
    (hγC : ContinuousOn γ (Set.Icc 0 1))
    (hγU : Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T)) :
    ∃ ρ : ℂ → ℝ,
      (∀ a ∈ T, 0 < ρ a) ∧
      (∀ a ∈ T, ρ a < r a) ∧
      (∀ a ∈ T, Disjoint (Metric.closedBall a (ρ a)) (γ '' Set.Icc (0:ℝ) 1)) ∧
      (∀ a ∈ T, ∀ b ∈ T, a ≠ b →
        Disjoint (Metric.closedBall a (ρ a)) (Metric.closedBall b (ρ b)))  := by
  have h_inf : ∀ a ∈ T, 0 < Metric.infDist a (γ '' Set.Icc (0:ℝ) 1) :=
    infdist_gamma_image_pos r hr_pos hγC hγU
  obtain ⟨d, hd_pos, hd_dist⟩ : ∃ d : ℝ, 0 < d ∧ ∀ a ∈ T, ∀ b ∈ T, a ≠ b → d ≤ dist a b :=
    pairwise_pole_lower_bound r hr_pos hγC hγU

  refine ⟨fun a => min (r a / 2) (min (Metric.infDist a (γ '' Set.Icc (0:ℝ) 1) / 2) (d / 4)),
    ?_, ?_, ?_, ?_⟩
  · intro a ha
    have h1 := hr_pos a ha
    have h2 := h_inf a ha
    exact lt_min_iff.mpr ⟨by linarith, lt_min_iff.mpr ⟨by linarith, by linarith⟩⟩
  · intro a ha
    have h1 := hr_pos a ha
    calc min (r a / 2) _ ≤ r a / 2 := min_le_left _ _
      _ < r a := by linarith
  · intro a ha
    apply Metric.disjoint_closedBall_of_lt_infDist
    have h2 := h_inf a ha
    calc min (r a / 2) (min (Metric.infDist a (γ '' Set.Icc (0:ℝ) 1) / 2) (d / 4))
        ≤ min (Metric.infDist a (γ '' Set.Icc (0:ℝ) 1) / 2) (d / 4) := min_le_right _ _
      _ ≤ Metric.infDist a (γ '' Set.Icc (0:ℝ) 1) / 2 := min_le_left _ _
      _ < Metric.infDist a (γ '' Set.Icc (0:ℝ) 1) := by linarith
  · intro a ha b hb hab
    apply Metric.closedBall_disjoint_closedBall
    have h_ab := hd_dist a ha b hb hab
    have h_a : min (r a / 2) (min (Metric.infDist a (γ '' Set.Icc (0:ℝ) 1) / 2) (d / 4)) ≤ d / 4 :=
      (min_le_right _ _).trans (min_le_right _ _)
    have h_b : min (r b / 2) (min (Metric.infDist b (γ '' Set.Icc (0:ℝ) 1) / 2) (d / 4)) ≤ d / 4 :=
      (min_le_right _ _).trans (min_le_right _ _)
    linarith


end Problems.residue_thm
