import Mathlib
import Problems.residue_thm.Defs
import Problems.residue_thm.proofs.L_per_pole_punctured_analytic_radius
import Problems.residue_thm.proofs.L_residue_thm_reduction
import Problems.residue_thm.proofs.L_winding_integral_integrality

namespace Problems.residue_thm

-- Decompose into: (1) per-pole punctured analytic radius for `f`, (2) winding-number
-- integral integrality for each pole (closed C¹ curve avoiding the pole),
-- (3) the residue-theorem reduction step that combines per-pole data with the
-- simply-connected + analyticity hypotheses.
theorem s10278 : ∀ {U : Set ℂ} {T : Finset ℂ} {f : ℂ → ℂ} {γ : ℝ → ℂ},
  IsOpen U → SimplyConnectedSpace ↥U →
  (∀ a ∈ T, a ∈ U) →
  AnalyticOn ℂ f (U \ ↑T) →
  ContDiffOn ℝ 1 γ (Set.Icc 0 1) →
  Set.MapsTo γ (Set.Icc 0 1) (U \ ↑T) →
  γ 0 = γ 1 →
  (∫ t in (0:ℝ)..1, f (γ t) * deriv γ t) = 2 * Real.pi * Complex.I *
    ∑ a ∈ T, (Complex.windingNumber γ a : ℂ) * Complex.residue f a  := by
  intro U T f γ hU hsc hT hf hγ hmap hclosed
  have h_radius : ∀ a ∈ T, ∃ R : ℝ, 0 < R ∧ AnalyticOn ℂ f (Metric.ball a R \ {a}) :=
    fun a ha => per_pole_punctured_analytic_radius hU hT hf a ha
  have h_winding : ∀ a ∈ T, ∃ k : ℤ,
      (∫ t in (0:ℝ)..1, deriv γ t / (γ t - a)) = 2 * Real.pi * Complex.I * k :=
    fun a ha => winding_integral_integrality hU hT hγ hmap hclosed a ha
  exact residue_thm_reduction hU hsc hT hf hγ hmap hclosed h_radius h_winding



end Problems.residue_thm
